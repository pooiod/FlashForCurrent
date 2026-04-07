function hasRuffleScript() {
  var headScripts = document.head.getElementsByTagName('script');
  for (var i = 0; i < headScripts.length; i++) {
    if (headScripts[i].getAttribute('src') === '/_static/js/ruffle.js') {
      return true;
    }
  }
  return false;
}

if (hasRuffleScript()) {
  var headScripts = document.head.getElementsByTagName('script');
  for (var i = 0; i < headScripts.length; i++) {
    if (headScripts[i].getAttribute('src') === '/_static/js/ruffle.js') {
      headScripts[i].parentNode.removeChild(headScripts[i]);
      console.log("Ruffle script removed from the page.");
      break;
    }
  }
}
