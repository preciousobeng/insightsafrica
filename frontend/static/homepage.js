
/* Homepage only. All observations are precomputed; no anomaly API calls. */
(function () {
'use strict';
const $ = (id) => document.getElementById(id);
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
const themeButton = $('theme-btn');
function themeLabel() { themeButton.textContent = document.documentElement.dataset.theme === 'light' ? 'Dark view' : 'Light view'; }
themeLabel();
themeButton.addEventListener('click', () => {
 const theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
 document.documentElement.dataset.theme = theme;
 try { localStorage.setItem('ia-theme', theme); } catch (_) {}
 themeLabel();
});
$('mine-range').addEventListener('input', (event) => {
 document.querySelector('.compare-before').style.clipPath = 'inset(0 ' + (100 - Number(event.target.value)) + '% 0 0)';
});
const colours = ['#8C510A','#D8B365','#F5F5F5','#5AB4AC','#01665E'];
const colour = d3.scaleLinear().domain([-50,-25,0,25,50]).range(colours).clamp(true);
const fmt = (v) => v == null ? 'not available' : Number(v).toFixed(1);
const monthName = (ym) => new Intl.DateTimeFormat('en', {month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(ym + '-01T00:00:00Z'));
const valueText = (value) => fmt(value[0]) + ' mm; ' + (value[1] == null ? 'normal unavailable' : fmt(value[1] + 100) + '% of normal (' + (value[1] >= 0 ? '+' : '') + fmt(value[1]) + '% departure)');
const escapeHTML = (v) => String(v).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function getJSON(url) { const response = await fetch(url); if (!response.ok) throw new Error('Data unavailable'); return response.json(); }
Promise.all([getJSON('/static/data/homepage_summary.json'),getJSON('/static/data/homepage_countries.topojson')]).then(([summary, topology]) => {
 const countries = Object.entries(summary.countries);
 const months = countries[0][1].recent_months;
 let index = months.length - 1;
 let timer = null;
 let regional = null;
 const shapes = Array.from(document.querySelectorAll('.country-shape'));
 const tooltip = $('map-tooltip');
 function stop() { clearInterval(timer); timer = null; $('play-months').textContent = 'Play 24 months'; $('play-months').setAttribute('aria-pressed','false'); }
 function showMonth(i, announce) {
  index = i;
  $('month-range').value = String(i);
  $('map-month').textContent = monthName(months[i]);
  $('month-range').setAttribute('aria-valuetext',monthName(months[i]));
  shapes.forEach((shape) => {
   const country = summary.countries[shape.dataset.country], value = country.recent_values[i];
   shape.querySelector('.map-fill').setAttribute('fill',value[1] == null ? '#A79F93' : colour(value[1]));
   const label = shape.querySelector('.map-code').textContent + ' · ' + country.name + ', ' + monthName(months[i]) + ': ' + valueText(value);
   shape.setAttribute('aria-label',label);
   shape.setAttribute('title',label);
  });
  if (regional) regional.selectAll('path').attr('fill',(feature) => {
   const region = summary.countries[feature.properties.country]?.regions[feature.id];
   const value = region?.recent[i]?.[1];
   return value == null ? '#A79F93' : colour(value);
  });
  if (announce) $('timeline-status').textContent = 'Map showing ' + monthName(months[i]);
  tooltip.hidden = true;
 }
 function play() {
  stop(); showMonth(0,false);
  $('play-months').textContent = 'Pause'; $('play-months').setAttribute('aria-pressed','true');
  timer = setInterval(() => { if (index >= months.length - 1) { stop(); return; } showMonth(index + 1,false); },750);
 }
 $('month-range').disabled = false; $('play-months').disabled = false;
 $('month-range').max = String(months.length - 1);
 $('month-range').addEventListener('input', (event) => { stop(); showMonth(Number(event.target.value),true); });
 $('play-months').addEventListener('click', () => { if (timer) stop(); else play(); });
 document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
 reduced.addEventListener('change', () => { if (reduced.matches) stop(); });
 // One pass only, beginning when the map is visible. User interaction cancels it.
 let interacted = false;
 ['pointerdown','keydown'].forEach((type) => $('hero-map').parentElement.addEventListener(type, () => { interacted = true; stop(); },{capture:true}));
 if (!reduced.matches) {
  const observer = new IntersectionObserver((entries) => {
   if (entries.some((entry) => entry.isIntersecting)) { observer.disconnect(); if (!interacted) play(); }
  },{threshold:.15});
  observer.observe($('hero-map'));
 }
 showMonth(index,false);
 shapes.forEach((shape) => {
  function show(event) {
   tooltip.textContent = shape.getAttribute('aria-label'); tooltip.hidden = false;
   const rect = shape.getBoundingClientRect();
   const x = event.clientX || rect.left, y = event.clientY || rect.top;
   tooltip.style.left = Math.max(8,Math.min(window.innerWidth - 285,x + 15)) + 'px';
   tooltip.style.top = Math.max(8,Math.min(window.innerHeight - 110,y + 15)) + 'px';
  }
  shape.addEventListener('pointermove',show); shape.addEventListener('focus',show);
  shape.addEventListener('pointerleave',() => { tooltip.hidden = true; });
  shape.addEventListener('blur',() => { tooltip.hidden = true; });
 });
 document.addEventListener('keydown',(event) => { if (event.key === 'Escape') tooltip.hidden = true; });
 // Optional region geometry is an explicit post-TD-3 configuration. A missing file
 // never prevents the public-domain country fallback from rendering.
 if (summary.region_geometry_url) {
  getJSON(summary.region_geometry_url).then((regions) => {
   const features = topojson.feature(regions,regions.objects.regions).features;
   const svg = d3.select('.atlas-map--desktop');
   const radians = (v) => v * Math.PI / 180, merc = (v) => Math.log(Math.tan(Math.PI/4 + radians(v)/2));
   const scale = Math.min(1052/radians(81),602/(merc(38)-merc(-36)));
   const projection = d3.geoMercator().scale(scale).translate([(1100-radians(81)*scale)/2-radians(-27)*scale,(650-(merc(38)-merc(-36))*scale)/2+merc(38)*scale]);
   if (!features.length || features.some((feature) => !summary.countries[feature.properties.country]?.regions[feature.id])) throw new Error('Regional keys do not match');
   regional = svg.append('g').attr('class','region-layer');
   regional.selectAll('path').data(features).join('path').attr('d',d3.geoPath(projection)).attr('stroke','var(--bg)').attr('stroke-width',.6).append('title').text((feature) => {
    const country = summary.countries[feature.properties.country], region = country?.regions[feature.id];
    return region ? region.name + ': ' + valueText(region.value) : 'No matching observation';
   });
   $('map-mode').textContent = 'Regional view · country fallback on small screens';
   showMonth(index,false);
  }).catch(() => { $('map-mode').textContent = 'Country view · regional outlines unavailable'; });
 }
 const countryFeatures = topojson.feature(topology,topology.objects.countries).features;
 let activeCountry = countries[0][0];
 const tabs = d3.select('#country-tabs').selectAll('button').data(countries).join('button')
  .attr('type','button').attr('class','country-tab').attr('role','tab').attr('id',(d) => 'tab-' + d[0]).attr('aria-controls','rain-chart-panel');
 tabs.each(function ([code,country]) {
  const feature = countryFeatures.find((f) => f.properties.country === code);
  const svg = d3.select(this).append('svg').attr('viewBox','0 0 70 40').attr('aria-hidden','true');
  svg.append('path').attr('d',d3.geoPath(d3.geoMercator().fitExtent([[2,2],[68,38]],feature))(feature));
  d3.select(this).append('span').text(country.name);
 });
 function chart(code, focus) {
  activeCountry = code;
  tabs.attr('aria-selected',(d) => String(d[0] === code)).attr('tabindex',(d) => d[0] === code ? 0 : -1);
  $('rain-chart-panel').setAttribute('aria-labelledby','tab-' + code);
  if (focus) $('tab-' + code).focus();
  const country = summary.countries[code], latestYear = Number(country.latest.slice(0,4));
  $('chart-country').textContent = country.name + ' · rainfall in mm';
  $('current-year-label').textContent = latestYear;
  const years = new Map();
  country.months.forEach((ym,i) => {
   const year = Number(ym.slice(0,4)), month = Number(ym.slice(5)) - 1;
   if (!years.has(year)) years.set(year,Array(12).fill(null));
   years.get(year)[month] = country.national[i];
  });
  const width = 1000, height = 350, margin = {left:48,right:15,top:18,bottom:35};
  const x = d3.scaleLinear().domain([0,11]).range([margin.left,width-margin.right]);
  const high = Math.max(...country.national.filter((v) => v != null),...country.normal.map((v) => (v[0] || 0) + (v[1] || 0)));
  const y = d3.scaleLinear().domain([0,high*1.06]).nice().range([height-margin.bottom,margin.top]);
  const host = d3.select('#rain-chart'); host.selectAll('*').remove();
  const svg = host.append('svg').attr('viewBox','0 0 ' + width + ' ' + height).attr('role','img').attr('aria-label',country.name + ' monthly rainfall from 1981 to ' + latestYear + '; exact values in tables below');
  y.ticks(5).forEach((tick) => {
   svg.append('line').attr('class','chart-grid').attr('x1',margin.left).attr('x2',width-margin.right).attr('y1',y(tick)).attr('y2',y(tick));
   svg.append('text').attr('class','chart-axis').attr('x',margin.left-8).attr('y',y(tick)+4).attr('text-anchor','end').text(tick);
  });
  const monthLabels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  monthLabels.forEach((label,i) => svg.append('text').attr('class','chart-axis').attr('x',x(i)).attr('y',height-8).attr('text-anchor','middle').text(label));
  const band = d3.area().defined((d) => d[0] != null && d[1] != null).x((d,i) => x(i)).y0((d) => y(Math.max(0,d[0]-d[1]))).y1((d) => y(d[0]+d[1]));
  svg.append('path').attr('class','normal-band').attr('d',band(country.normal));
  const line = d3.line().defined((d) => d != null).x((d,i) => x(i)).y((d) => y(d));
  years.forEach((values,year) => { if (year < latestYear) svg.append('path').attr('class','past-line').attr('d',line(values)); });
  svg.append('path').attr('class','normal-line').attr('d',line(country.normal.map((v) => v[0])));
  svg.append('path').attr('class','current-line').attr('d',line(years.get(latestYear)));
  function reading(month,year) {
   $('chart-readout').textContent = country.name + ' · ' + monthLabels[month] + ' ' + year + ': ' + fmt(years.get(year)[month]) + ' mm. 1991–2020 mean ' + fmt(country.normal[month][0]) + ' mm; standard deviation ' + fmt(country.normal[month][1]) + ' mm.';
  }
  svg.on('pointermove',(event) => {
   const [px,py] = d3.pointer(event,svg.node()), month = Math.max(0,Math.min(11,Math.round(x.invert(px))));
   const available = Array.from(years).filter(([,values]) => values[month] != null);
   const nearest = available.reduce((best,row) => Math.abs(y(row[1][month])-py) < Math.abs(y(best[1][month])-py) ? row : best);
   reading(month,nearest[0]);
  });
  const controls = host.append('div').attr('class','chart-month-controls').attr('aria-label','Latest-year monthly readings');
  monthLabels.forEach((label,month) => controls.append('button').attr('type','button').text(label).attr('aria-label',label + ' ' + latestYear + ' exact rainfall').on('focus',() => reading(month,latestYear)).on('click',() => reading(month,latestYear)));
  reading(Number(country.latest.slice(5))-1,latestYear);
 }
 tabs.on('click',(_,d) => chart(d[0],false)).on('keydown',(event,d) => {
  let i = countries.findIndex((c) => c[0] === d[0]);
  if (event.key === 'ArrowRight') i = (i+1)%countries.length;
  else if (event.key === 'ArrowLeft') i = (i+countries.length-1)%countries.length;
  else if (event.key === 'Home') i = 0; else if (event.key === 'End') i = countries.length-1; else return;
  event.preventDefault(); chart(countries[i][0],true);
 });
 chart(activeCountry,false);
 const allPlaces = countries.flatMap(([code,country]) => country.places.map((place) => ({...place,country:code,countryName:country.name})));
 const normalize = (text) => text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
 const search = $('place-search'), list = $('place-results'); let matches = [], selected = -1;
 search.disabled = false;
 function closeList() { list.hidden = true; search.setAttribute('aria-expanded','false'); search.removeAttribute('aria-activedescendant'); }
 function choose(place) {
  closeList(); search.value = place.name;
  const [mm,pct] = place.value, country = summary.countries[place.country];
  $('place-card').hidden = false;
  $('place-card').innerHTML = '<p class="kicker">' + escapeHTML(place.countryName + ' · ' + place.level) + '</p><h3>' + escapeHTML(place.name) + '</h3><p>' + escapeHTML(monthName(country.latest)) + '</p><p class="place-values">' + fmt(mm) + ' mm</p><p>' + (pct == null ? 'Seasonal normal unavailable.' : fmt(pct+100) + '% of the 1991–2020 normal.') + '</p><p>' + (place.rank == null ? 'Rank unavailable.' : 'Ranked ' + place.rank + ' of ' + place.samples + ' observations for this calendar month since 1981 (1 = wettest; ties share a rank).') + '</p><p>' + (place.last_wetter ? 'Last as wet or wetter: ' + escapeHTML(String(place.last_wetter)) + '.' : 'No earlier as-wet observation in the available record.') + '</p><svg class="sparkline" viewBox="0 0 500 100" role="img" aria-label="Last 24 monthly rainfall totals"></svg><p class="source-line">CHIRPS v2.0 · public domain. Missing values remain gaps.</p><a class="button secondary" href="/' + place.country + '/flood/">Open ' + escapeHTML(place.countryName) + ' FloodWatch</a><p class="source-line">Opens the country view; choose your area there.</p>';
  const spark = d3.select('#place-card .sparkline'), x = d3.scaleLinear().domain([0,23]).range([5,495]), y = d3.scaleLinear().domain([0,Math.max(1,...place.recent.filter((v) => v != null))]).range([75,8]);
  spark.append('path').attr('class','spark-line').attr('d',d3.line().defined((v) => v != null).x((v,i) => x(i)).y((v) => y(v))(place.recent));
  spark.append('text').attr('class','spark-label').attr('x',5).attr('y',98).text(country.recent_months[0]);
  spark.append('text').attr('class','spark-label').attr('x',495).attr('y',98).attr('text-anchor','end').text(country.latest);
  $('search-status').textContent = 'Showing ' + place.name + ', ' + place.countryName + '.';
 }
 search.addEventListener('input',() => {
  const query = normalize(search.value); selected = -1; list.replaceChildren();
  if (query.length < 2) { closeList(); $('search-status').textContent = 'Type at least two characters.'; return; }
  matches = allPlaces.filter((place) => normalize(place.name + ' ' + place.parent + ' ' + place.countryName).includes(query)).slice(0,12);
  matches.forEach((place,i) => {
   const item = document.createElement('li'); item.id = 'place-option-' + i; item.setAttribute('role','option'); item.setAttribute('aria-selected','false');
   item.textContent = place.name + (place.parent ? ', ' + place.parent : '') + ' · ' + place.countryName + ' (' + place.level + ')';
   item.addEventListener('click',() => choose(place)); list.append(item);
  });
  list.hidden = !matches.length; search.setAttribute('aria-expanded',String(!!matches.length));
  $('search-status').textContent = matches.length ? matches.length + ' matches shown. Use arrow keys then Enter to choose.' : 'No matching area. Try a region or country name.';
 });
 search.addEventListener('keydown',(event) => {
  if (event.key === 'Escape') { closeList(); return; }
  if (list.hidden) return;
  if (event.key === 'Enter' && selected >= 0) { event.preventDefault(); choose(matches[selected]); return; }
  if (!['ArrowDown','ArrowUp'].includes(event.key)) return;
  event.preventDefault(); selected = (selected + (event.key === 'ArrowDown' ? 1 : -1) + matches.length)%matches.length;
  Array.from(list.children).forEach((item,i) => item.setAttribute('aria-selected',String(i === selected)));
  search.setAttribute('aria-activedescendant','place-option-' + selected);
  list.children[selected].scrollIntoView({block:'nearest'});
 });
 search.addEventListener('blur',() => setTimeout(closeList,180));
}).catch(() => {
 $('search-status').textContent = 'Interactive data could not load. Country links, tables and CSV remain available.';
 $('map-mode').textContent = 'Latest saved country view · interactive data unavailable';
});
})();
