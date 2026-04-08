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
      const [r,g,b]=theme.background.match(/\d+/g).map(Number);
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
