(function () {
  var headScripts = document.head.getElementsByTagName('script');
  for (var i = 0; i < headScripts.length; i++) {
    if (headScripts[i].getAttribute('src') && headScripts[i].getAttribute('src').includes("ruffle.js")) {
      headScripts[i].parentNode.removeChild(headScripts[i]);
      console.log("Ruffle script removed from the page.");
      break;
    }
  }

  const erudascript = document.createElement('script');
  erudascript.src = 'https://cdn.jsdelivr.net/npm/eruda';
  erudascript.onload = function () {
    eruda.init();
    var j38180310 = setInterval(()=>{
      const btn = document.querySelector('.eruda-entry-btn');
      if (btn) btn.style.display = 'none';
    }, 100);
    setTimeout(()=>{
      clearInterval(j38180310);
    }, 3000);
    setTimeout(()=>{
      const [r,g,b]=window.FlashTheme283.background.match(/\d+/g).map(Number);
      const brightness=(r*299+g*587+b*114)/1000;

      if(brightness>230) eruda.setTheme("Light");
      else if(brightness>200) eruda.setTheme("Material Lighter");
      else if(brightness>170) eruda.setTheme("Solarized Light");
      else if(brightness>140) eruda.setTheme("Github");
      else if(brightness>110) eruda.setTheme("Material Oceanic");
      else if(brightness>90) eruda.setTheme("Atom One Light");
      else if(brightness>70) eruda.setTheme("Material Palenight");
      else if(brightness>50) eruda.setTheme("Dracula");
      else if(brightness>35) eruda.setTheme("Monokai Pro");
      else if(brightness>20) eruda.setTheme("Atom One Dark");
      else if(brightness>10) eruda.setTheme("Material Deep Ocean");
      else eruda.setTheme("AMOLED");
    }, 1000);
  };
  document.head.appendChild(erudascript);

  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'i') {
      if (window.eruda) {
        if (eruda._isShow) {
          eruda.hide();
        } else {
          eruda.show();
        }
      }
    }
  });
})();
