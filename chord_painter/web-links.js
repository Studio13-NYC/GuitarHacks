(function(){
  if(window.qt?.webChannelTransport)return;
  const footer=document.createElement('footer');footer.className='web-project-links';footer.setAttribute('aria-label','Downloads and GitHub projects');
  const icon=document.createElement('img');icon.src='github.svg';icon.alt='';icon.width=24;icon.height=24;footer.append(icon);
  for(const [label,url] of [
    ['Windows desktop download','https://github.com/Studio13-NYC/GuitarHacks/releases/tag/v0.1.0-alpha.1'],
    ['GuitarHacks on GitHub','https://github.com/Studio13-NYC/GuitarHacks'],
    ['More Studio13 projects','https://github.com/orgs/Studio13-NYC/repositories']
  ]){const a=document.createElement('a');a.textContent=label;a.href=url;a.target='_blank';a.rel='noopener';footer.append(a);}
  document.body.append(footer);
})();
