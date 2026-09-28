const defaults = {palette:'forest',theme:'light',avatar:'letter'};
export function setupAppearance() {
  let value = defaults;
  try { value = {...defaults, ...JSON.parse(localStorage.getItem('nexo-browser-appearance') || '{}')}; } catch {}
  const choices = {palette:['forest','ocean','violet','rose','amber'],theme:['light','dark'],avatar:['letter','robot','cat','orb']};
  function apply() {
    for (const name of Object.keys(choices)) {
      if (!choices[name].includes(value[name])) value[name] = defaults[name];
      document.documentElement.dataset[name] = value[name];
      document.getElementById('browser-'+name).value = value[name];
    }
  }
  for (const name of Object.keys(choices)) {
    document.getElementById('browser-'+name).onchange = event => {
      value[name] = event.target.value;
      apply();
      try { localStorage.setItem('nexo-browser-appearance', JSON.stringify(value)); } catch {}
    };
  }
  apply();
}
