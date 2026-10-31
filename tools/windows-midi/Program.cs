using System.Collections.Concurrent;
using System.Text.Json;
using Microsoft.Windows.Devices.Midi2;
using Microsoft.Windows.Devices.Midi2.Endpoints.Loopback;
using Microsoft.Windows.Devices.Midi2.Initialization;

// Newline-delimited JSON over private process pipes. No network listener.
// Keep IO off the MIDI callback thread; overflow is a fatal, visible error.
using var events = new BlockingCollection<object>(8192);
var gate = new object();
int overflow = 0;
var disconnected = false;
void Emit(object value)
{
    lock (gate)
    {
        if (!events.IsAddingCompleted && !events.TryAdd(value)) Interlocked.Exchange(ref overflow, 1);
    }
}
var writer = Task.Run(() =>
{
    foreach (var value in events.GetConsumingEnumerable())
    {
        if (Interlocked.Exchange(ref overflow, 0) != 0)
            Console.WriteLine(JsonSerializer.Serialize(new { type = "error", message = "MIDI queue overflow. Take is incomplete." }));
        Console.WriteLine(JsonSerializer.Serialize(value));
        Console.Out.Flush();
    }
});

int result = 0;
try
{
    string configPath = args.Length == 1 ? args[0] : Path.Combine(AppContext.BaseDirectory, "loopback.json");
    var config = JsonSerializer.Deserialize<LoopbackConfig>(File.ReadAllText(configPath),
        new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
    using var initializer = MidiDesktopAppSdkInitializer.Create()
        ?? throw new Exception("Windows MIDI Services SDK initializer is unavailable.");
    if (!initializer.InitializeSdkRuntime()) throw new Exception("Windows MIDI Services SDK runtime could not initialize. Install matching RC4 runtime.");
    if (!initializer.EnsureServiceAvailable()) throw new Exception("Windows MIDI Service is unavailable.");
    if (!MidiLoopbackEndpointManager.IsTransportAvailable) throw new Exception("Microsoft LOOP transport is unavailable.");

    // Use returned device IDs and association metadata, never a port list index.
    var endpoints = MidiEndpointDeviceInformation.FindAll()
        .Where(e => e.GetTransportSuppliedInfo().TransportId == MidiLoopbackEndpointManager.TransportId
            && MidiLoopbackEndpointManager.GetAssociationId(e) == config.AssociationId).ToList();
    if (endpoints.Count == 0)
    {
        var creation = MidiLoopbackEndpointManager.CreateTransientLoopbackEndpoints(new MidiLoopbackEndpointCreationConfig
        {
            AssociationId = config.AssociationId,
            EndpointDefinitionA = new MidiLoopbackEndpointDefinition { Name = config.NameA, UniqueId = config.UniqueId },
            EndpointDefinitionB = new MidiLoopbackEndpointDefinition { Name = config.NameB, UniqueId = config.UniqueId }
        });
        if (!creation.Success) throw new Exception("Could not create Microsoft loopback: " + creation.ErrorInformation);
        endpoints = new() {
            MidiEndpointDeviceInformation.CreateFromEndpointDeviceId(creation.EndpointDeviceIdA),
            MidiEndpointDeviceInformation.CreateFromEndpointDeviceId(creation.EndpointDeviceIdB) };
    }
    var send = endpoints.SingleOrDefault(e => e.Name == config.NameA);
    var receive = endpoints.SingleOrDefault(e => e.Name == config.NameB);
    if (send == null || receive == null || endpoints.Count != 2)
        throw new Exception("The saved GuitarHacks loopback is incomplete or renamed. Check MIDI Settings; no existing endpoint was modified.");

    using var session = MidiSession.Create("GuitarHacks Jam recorder");
    var connection = session.CreateEndpointConnection(receive.EndpointDeviceId);
    connection.MessageReceived += (_, message) =>
    {
        try
        {
            var words = new List<uint>(4);
            message.AppendWordsToList(words);
            Emit(new { type = "midi", timestamp = message.Timestamp, words });
        }
        catch (Exception error) { Emit(new { type = "error", message = error.Message }); }
    };
    connection.EndpointDeviceDisconnected += (_, _) => {
        disconnected = true;
        Emit(new { type = "error", message = "MIDI endpoint disconnected. Reconnect before recording another take." });
    };
    if (!connection.Open()) throw new Exception("Could not open GuitarHacks receive endpoint.");
    Emit(new { type = "ready", timestamp = MidiClock.Now, frequency = MidiClock.TimestampFrequency,
        endpoint = receive.EndpointDeviceId, sendEndpoint = send.EndpointDeviceId,
        name = receive.Name, sendName = send.Name, sdk = "1.0.17-rc.4.25" });

    // Commands are clock markers in the same event stream as MIDI messages.
    // stdin EOF disposes the session when the parent exits.
    while (Console.ReadLine() is string command)
    {
        if (command == "quit") break;
        if (disconnected) break;
        if (command is "start" or "stop")
            Emit(new { type = command, timestamp = MidiClock.Now });
    }
    session.DisconnectEndpointConnection(connection.ConnectionId);
}
catch (Exception error)
{
    Emit(new { type = "error", message = error.Message });
    result = 1;
}
finally
{
    events.CompleteAdding();
    await writer;
}
return result;

record LoopbackConfig(Guid AssociationId, string UniqueId, string NameA, string NameB);
