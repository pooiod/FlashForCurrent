(function () {
  const getThemeColors = () => {
    let style = getComputedStyle(document.body).backgroundColor;
    if (!style || style === "transparent" || style === "rgba(0, 0, 0, 0)") {
      style = "rgb(255,255,255)";
    } else if (style.startsWith("rgba")) {
      let parts = style.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+\.?\d*)\)/);
      let r = Math.round(255 * (1 - parseFloat(parts[4])) + parseInt(parts[1]) * parseFloat(parts[4]));
      let g = Math.round(255 * (1 - parseFloat(parts[4])) + parseInt(parts[2]) * parseFloat(parts[4]));
      let b = Math.round(255 * (1 - parseFloat(parts[4])) + parseInt(parts[3]) * parseFloat(parts[4]));
      style = `rgb(${r},${g},${b})`;
    }

    const bgColor = style;
    const tempElem = document.createElement("div");
    tempElem.style.color = bgColor;
    document.body.appendChild(tempElem);
    const rgbStyle = window.getComputedStyle(tempElem).color;
    document.body.removeChild(tempElem);

    const rgbValues = rgbStyle.match(/\d+/g).map(Number);
    const r = rgbValues[0] / 255;
    const g = rgbValues[1] / 255;
    const b = rgbValues[2] / 255;

    const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    const textColor = luminance > 0.5 ? "#000000" : "#ffffff";

    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;

    if (max === min) {
      h = s = 0;
    } else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = (g - b) / d + (g < b ? 6 : 0); break;
        case g: h = (b - r) / d + 2; break;
        case b: h = (r - g) / d + 4; break;
      }
      h /= 6;
    }

    h *= 360;
    s *= 100;
    l *= 100;

    let accentHue = (h + 180) % 360;
    let accentSat = s < 10 ? 75 : Math.min(s + 20, 100);
    let accentLight;

    if (l > 70) {
      accentLight = 40;
    } else if (l < 30) {
      accentLight = 70;
    } else {
      accentLight = l > 50 ? l - 30 : l + 30;
    }

    if (s < 10) {
      accentHue = 210;
      accentSat = 80;
    }

    const accentColor = `hsl(${Math.round(accentHue)}, ${Math.round(accentSat)}%, ${Math.round(accentLight)}%)`;

    return {
      background: bgColor,
      accent: accentColor,
      text: textColor
    };
  };

  const theme = getThemeColors();

  var headScripts = document.head.getElementsByTagName('script');
  for (var i = 0; i < headScripts.length; i++) {
    if (headScripts[i].getAttribute('src') && headScripts[i].getAttribute('src').includes("ruffle.js")) {
      headScripts[i].parentNode.removeChild(headScripts[i]);
      console.log("Ruffle script removed from the page.");
      break;
    }
  }

  if (!window.eruda) {
    const erudascript = document.createElement('script');
    erudascript.src = 'https://cdn.jsdelivr.net/npm/eruda';
    erudascript.onload = function () {
      const [r,g,b]=theme.background.match(/\d+/g).map(Number);
      const brightness=(r*299+g*587+b*114)/1000;

      const erudaTheme =
        brightness>230?"Light":
        brightness>200?"Material Lighter":
        brightness>170?"Solarized Light":
        brightness>140?"Github":
        brightness>110?"Material Oceanic":
        brightness>90?"Atom One Light":
        brightness>70?"Material Palenight":
        brightness>50?"Dracula":
        brightness>35?"Monokai Pro":
        brightness>20?"Atom One Dark":
        brightness>10?"Material Deep Ocean":
      "AMOLED";

      eruda.init({defaults: {
        theme: erudaTheme
      }});

      document.addEventListener('keydown', function (event) {
        if (event.ctrlKey && event.shiftKey && event.key === 'I') {
          if (eruda._isShow) {
            eruda.hide();
            eruda._isShow = false;
          } else {
            eruda.show();
            eruda._isShow = true;
          }
        }
      });

      var j38180310 = setInterval(()=>{
        document.querySelector("#eruda").shadowRoot.querySelector("div.eruda-entry-btn").style.display = "none";
      }, 100);
      setTimeout(()=>{
        clearInterval(j38180310);
      }, 3000);
      setTimeout(()=>{
        eruda.settings.set('theme', erudaTheme);
      }, 1000);
    };
    document.head.appendChild(erudascript);
  }

  document.addEventListener('keydown', function(event) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'r') {
      window.location.reload();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'w') {
      window.location.href == "https://flashforcurrent.pages.dev/blank";
    }
  });
})();
