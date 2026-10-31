#include <muscriptor/muscriptor.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <vector>
#include <cmath>
#include <algorithm>
#include <string>
#include <array>
#include <sstream>
#include <limits>
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>

static std::string sha256_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input) throw std::runtime_error("Cannot open note events for verification");
    const auto size = input.tellg();
    if (size < 0 || static_cast<unsigned long long>(size) > std::numeric_limits<ULONG>::max())
        throw std::runtime_error("Invalid note event file size");
    std::vector<unsigned char> bytes(static_cast<std::size_t>(size));
    input.seekg(0);
    if (!input.read(reinterpret_cast<char*>(bytes.data()), size))
        throw std::runtime_error("Cannot read note events for verification");
    std::array<unsigned char, 32> digest{};
    if (BCryptHash(BCRYPT_SHA256_ALG_HANDLE, nullptr, 0, bytes.data(),
                   static_cast<ULONG>(bytes.size()), digest.data(), static_cast<ULONG>(digest.size())) < 0)
        throw std::runtime_error("Cannot hash note events");
    std::ostringstream hex;
    hex << std::hex << std::setfill('0');
    for (auto byte : digest) hex << std::setw(2) << static_cast<unsigned int>(byte);
    return hex.str();
}

// Paths use wide Windows arguments, including song titles with non-ASCII names.
int wmain(int argc, wchar_t** argv) {
    try {
        if (argc == 2 && std::wstring(argv[1]) == L"--list-instruments") {
            for (auto group : msl::allInstrumentGroups())
                std::cout << msl::instrumentName(group) << '\n';
            return 0;
        }
        if (argc < 4) {
            std::cerr << "Usage: guitarhacks-transcribe model.gguf mono-16000.f32 notes.tsv [--instruments all|name,name]\n";
            return 2;
        }
        msl::TranscribeOptions options;
        options.n_threads = 8;
        if (argc > 4) {
            if (std::wstring(argv[4]) != L"--instruments" || argc != 6)
                throw std::runtime_error("--instruments requires one comma-separated instrument list or all");
            const std::wstring selection(argv[5]);
            if (selection != L"all") {
                std::size_t start = 0;
                while (true) {
                    auto end = selection.find(L',', start);
                    auto wide = selection.substr(start, end == std::wstring::npos ? end : end - start);
                    std::string name;
                    for (wchar_t character : wide) {
                        if (character > 127) throw std::runtime_error("Unknown instrument name (use --list-instruments)");
                        name.push_back(static_cast<char>(character));
                    }
                    if (name.empty()) throw std::runtime_error("Empty instrument name");
                    const auto groups = msl::allInstrumentGroups();
                    auto found = std::find_if(groups.begin(), groups.end(), [&](auto group) {
                        return msl::instrumentName(group) == name;
                    });
                    if (found == groups.end()) throw std::runtime_error("Unknown instrument name: " + name);
                    if (std::find(options.instruments.begin(), options.instruments.end(), *found) == options.instruments.end())
                        options.instruments.push_back(*found);
                    if (end == std::wstring::npos) break;
                    start = end + 1;
                }
            }
        }
        std::cout << "INSTRUMENTS ";
        if (options.instruments.empty()) std::cout << "all";
        for (std::size_t i = 0; i < options.instruments.size(); ++i)
            std::cout << (i ? "," : "") << msl::instrumentName(options.instruments[i]);
        std::cout << std::endl;
        std::ifstream input(std::filesystem::path(argv[2]), std::ios::binary | std::ios::ate);
        if (!input) throw std::runtime_error("Cannot open decoded audio");
        auto bytes = input.tellg();
        if (bytes <= 0 || bytes % sizeof(float)) throw std::runtime_error("Invalid float32 audio");
        std::vector<float> samples(static_cast<size_t>(bytes) / sizeof(float));
        input.seekg(0);
        if (!input.read(reinterpret_cast<char*>(samples.data()), bytes))
            throw std::runtime_error("Cannot read decoded audio");
        for (float value : samples) if (!std::isfinite(value)) throw std::runtime_error("Non-finite audio");
        msl::LoadOptions load;
        int last = -1;
        load.on_progress = [&](float p) {
            int percent = static_cast<int>(p * 100);
            if (percent != last) { std::cout << "MODEL_PROGRESS " << percent << std::endl; last = percent; }
        };
        auto model = msl::Transcriber::load(std::filesystem::path(argv[1]), load);
        if (!model) throw std::runtime_error(std::string(msl::describe(model.error())));
        std::cout << "DEVICE " << model->device().backend << " / " << model->device().name << std::endl;
        auto notes = model->transcribe(samples, options, [](const msl::TranscriptionUpdate& update) {
            std::cout << "MIDI_PROGRESS " << static_cast<int>(update.progress * 100) << std::endl;
            return true;
        });
        if (!notes) throw std::runtime_error(std::string(msl::describe(notes.error())));
        std::ofstream output(std::filesystem::path(argv[3]), std::ios::binary);
        if (!output) throw std::runtime_error("Cannot write note events");
        output << "onset\toffset\tpitch\tprogram\tis_drum\tinstrument\n" << std::setprecision(12);
        for (const auto& note : *notes)
            output << note.onset << '\t' << note.offset << '\t' << note.pitch << '\t'
                   << note.program << '\t' << note.is_drum << '\t' << msl::instrumentLabel(note.program) << '\n';
        output.flush();
        if (!output) throw std::runtime_error("Could not save note events");
        output.close();
        if (!output) throw std::runtime_error("Could not close note events");
        const auto notes_sha256 = sha256_file(std::filesystem::path(argv[3]));
        auto settings_path = std::filesystem::path(argv[3]);
        settings_path.replace_extension(".settings.json");
        std::ofstream settings(settings_path, std::ios::binary);
        settings << "{\"instruments\":[";
        for (std::size_t i = 0; i < options.instruments.size(); ++i)
            settings << (i ? "," : "") << '\"' << msl::instrumentName(options.instruments[i]) << '\"';
        settings << "],\"decoder\":\"greedy\",\"prelude_forcing\":true,\"notes_sha256\":\""
                 << notes_sha256 << "\"}\n";
        settings.flush();
        if (!settings) throw std::runtime_error("Could not save transcription settings");
        std::cout << "NOTES " << notes->size() << std::endl;
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Transcription failed: " << error.what() << std::endl;
        return 1;
    }
}
