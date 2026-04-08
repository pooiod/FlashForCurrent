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
