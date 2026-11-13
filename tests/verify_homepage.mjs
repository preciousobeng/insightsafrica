/** Local-only browser evidence. Never submits a real contact message. */
import {createRequire} from 'node:module';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const puppeteer=require(process.env.HOMEPAGE_PUPPETEER || 'puppeteer-core');
const axePath=process.env.HOMEPAGE_AXE || require.resolve('axe-core/axe.min.js');
const base=process.env.HOMEPAGE_URL || 'http://127.0.0.1:8769';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname),'QA must target loopback');
const output='evidence/homepage';
fs.mkdirSync(output,{recursive:true});
const browser=await puppeteer.launch({executablePath:process.env.CHROME_PATH || '/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
const results={checks:[],accessibility:[],errors:[],requests:[]};
function check(name,condition){assert(condition,name);results.checks.push(name);}
async function pageFor(width=1440,theme='dark',motion='reduce'){
 const page=await browser.newPage();await page.setViewport({width,height:1000,deviceScaleFactor:1});
 await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:motion}]);
 const {identifier}=await page.evaluateOnNewDocument((theme)=>localStorage.setItem('ia-theme',theme),theme);page.themeScript=identifier;
 page.on('pageerror',error=>results.errors.push(error.message));
 await page.setRequestInterception(true);
 page.on('request',request=>{
  const url=new URL(request.url());
  if(url.protocol==='http:' && url.origin!==new URL(base).origin){results.errors.push('External request '+url);return request.abort();}
  if(url.protocol.startsWith('http'))results.requests.push(url.pathname);
  if(url.pathname==='/api/contact'){results.errors.push('Unexpected real contact request');return request.abort();}
  request.continue();
 });
 return page;
}
async function ready(page){await page.goto(base,{waitUntil:'networkidle0'});await page.waitForSelector('.current-line');await page.evaluate(()=>document.fonts.ready);if(page.themeScript){await page.removeScriptToEvaluateOnNewDocument(page.themeScript);page.themeScript=null;}}
async function loadImages(page){
 await page.evaluate(async()=>{
  document.querySelectorAll('img').forEach(img=>img.loading='eager');
  await Promise.all(Array.from(document.images).map(img=>img.decode().catch(()=>{})));
 });
}
try{
 for(const width of [375,768,1440]){
  for(const theme of ['dark','light']){
   const page=await pageFor(width,theme);await ready(page);await loadImages(page);
   check('Theme rendered '+width+' '+theme,await page.evaluate(theme=>document.documentElement.dataset.theme===theme,theme));
   check('No overflow '+width+' '+theme,await page.evaluate(()=>document.documentElement.scrollWidth===innerWidth));
   check('All watch images decode '+width+' '+theme,await page.evaluate(()=>Array.from(document.querySelectorAll('.watch-grid img')).every(img=>img.naturalWidth>0)));
   await page.addScriptTag({path:axePath});
   const axe=await page.evaluate(()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
   results.accessibility.push({width,theme,violations:axe.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
   await page.screenshot({path:output+'/'+width+'-'+theme+'.png',fullPage:true});
   if(width===375&&theme==='dark'){
    check('Reduced motion stays at latest month',await page.$eval('#month-range',e=>e.value==='23'));
    await new Promise(r=>setTimeout(r,1700));
    check('Reduced motion does not autoplay',await page.$eval('#month-range',e=>e.value==='23'));
    await page.screenshot({path:output+'/375-reduced-motion.png',fullPage:true});
   }
   await page.close();
  }
 }
 const page=await pageFor();await ready(page);
 const data=await page.evaluate(async()=>fetch('/static/data/homepage_summary.json').then(r=>r.json()));
 check('Natural Earth country fallback',await page.$eval('#map-mode',e=>e.textContent.includes('Country view')));
 check('No public regional file configured',data.region_geometry_url===null);
 await page.focus('#month-range');await page.keyboard.press('ArrowLeft');
 check('Keyboard timeline changes one month',await page.$eval('#month-range',e=>e.value==='22'));
 const displayed=await page.$eval('#map-month',e=>e.textContent);
 check('Timeline reading matches data',displayed.includes('August 2026'));
 const ghanaValue=data.countries.ghana.recent_values[22];
 check('Tooltip matches exact selected month',await page.$eval('.country-shape[data-country=ghana]',(e,value)=>e.getAttribute('aria-label').includes(value[0].toFixed(1)+' mm'),ghanaValue));
 await page.focus('#tab-ghana');await page.keyboard.press('ArrowRight');
 check('Country tabs work by keyboard',await page.$eval('#tab-nigeria',e=>e.getAttribute('aria-selected')==='true'&&e===document.activeElement));
 await page.click('#theme-btn');
 check('Theme preference persists',await page.evaluate(()=>localStorage.getItem('ia-theme')==='light'));
 await page.reload({waitUntil:'networkidle0'});
 check('Reload preserves light theme',await page.evaluate(()=>document.documentElement.dataset.theme==='light'));
 await page.type('#place-search','Tamale');await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
 const place=data.countries.ghana.places.find(p=>p.name==='Tamale'),card=await page.$eval('#place-card',e=>e.textContent);
 check('Search shows computed exact observation',card.includes(place.value[0].toFixed(1)+' mm'));
 check('Search shows computed rank',card.includes('Ranked '+place.rank+' of '+place.samples));
 check('Search does not invent a selected-district deep link',await page.$eval('#place-card a',e=>e.getAttribute('href')==='/ghana/flood/'));
 await page.$eval('#mine-range',e=>{e.value='80';e.dispatchEvent(new Event('input',{bubbles:true}))});
 check('Mine slider reveals actual before frame',await page.$eval('.compare-before',e=>e.style.clipPath.includes('20%')));
 await page.close();
 // Contact responses are intercepted locally; the real endpoint is never called.
 for(const mode of ['success','failure','network']){
  const contact=await browser.newPage();await contact.setRequestInterception(true);
  let payload;
  contact.on('request',request=>{
   if(new URL(request.url()).pathname==='/api/contact'){
    payload=JSON.parse(request.postData());
    if(mode==='network')request.abort();
    else request.respond({status:mode==='success'?200:400,contentType:'application/json',body:JSON.stringify(mode==='success'?{ok:true}:{detail:'Fixture rejection'})});
   }else request.continue();
  });
  await contact.goto(base,{waitUntil:'networkidle0'});
  await contact.type('#cf-name','QA Example');await contact.type('#cf-email','qa@example.invalid');await contact.select('#cf-type','General');await contact.type('#cf-msg','Local fixture only');
  await contact.click('#cf-btn');await contact.waitForFunction(()=>!document.querySelector('#cf-btn').disabled);
  assert.deepEqual(payload,{name:'QA Example',email:'qa@example.invalid',enquiry_type:'General',message:'Local fixture only'});
  results.checks.push('Contact payload unchanged '+mode);
  const feedback=await contact.$eval('#cf-feedback',e=>e.textContent);
  check('Contact feedback '+mode,mode==='success'?feedback.startsWith('Message sent'):mode==='failure'?feedback.includes('Fixture rejection'):feedback.length>0);
  check('Contact reset only on success '+mode,await contact.$eval('#cf-name',(e,mode)=>mode==='success'?e.value==='':e.value==='QA Example',mode));
  await contact.close();
 }
 const autoplay=await pageFor(1440,'dark','no-preference');await ready(autoplay);
 check('Timeline starts one automatic pass',await autoplay.$eval('#play-months',e=>e.getAttribute('aria-pressed')==='true'));
 await autoplay.waitForFunction(()=>document.querySelector('#month-range').value==='23' && document.querySelector('#play-months').getAttribute('aria-pressed')==='false',{timeout:25000});
 await new Promise(r=>setTimeout(r,1000));
 check('Timeline stops after one pass at latest month',await autoplay.$eval('#month-range',e=>e.value==='23'));
 await autoplay.close();
 const nojs=await browser.newPage();await nojs.setViewport({width:375,height:900});await nojs.setJavaScriptEnabled(false);await nojs.goto(base,{waitUntil:'networkidle0'});await loadImages(nojs);
 check('No-JS headline has latest date',await nojs.$eval('h1',e=>e.textContent.includes('September 2026')));
 check('No-JS has six historical tables',await nojs.$$eval('#historical-tables table',elements=>elements.length===6));
 check('No-JS has country map',await nojs.$$eval('.atlas-map--mobile .country-shape',elements=>elements.length===6));
 await nojs.screenshot({path:output+'/375-no-javascript.png',fullPage:true});await nojs.close();
 // Missing optional geometry must retain country shading and chart/search.
 const missing=await browser.newPage();await missing.setRequestInterception(true);
 missing.on('request',request=>{
  if(request.url().endsWith('/homepage_summary.json'))request.respond({status:200,contentType:'application/json',body:JSON.stringify({...data,region_geometry_url:'/static/data/missing-regions.topojson'})});
  else if(request.url().endsWith('/missing-regions.topojson'))request.respond({status:404,body:'Not available'});
  else request.continue();
 });
 await missing.goto(base,{waitUntil:'networkidle0'});await missing.waitForSelector('.current-line');
 check('Missing regions falls back to countries',await missing.$eval('#map-mode',e=>e.textContent.includes('regional outlines unavailable')));
 check('Missing regions retains filled countries',await missing.$$eval('.atlas-map--desktop .map-fill',elements=>elements.length===6));
 await missing.close();
 check('No runtime anomaly API or geometry downloads',!results.requests.some(path=>path.startsWith('/api/')||/gadm|districts\.geojson|regions\.geojson/.test(path)));
 check('No uncaught browser errors',results.errors.length===0);
 check('No WCAG A/AA axe violations',results.accessibility.every(result=>result.violations.length===0));
 fs.writeFileSync(output+'/browser-checks.json',JSON.stringify(results,null,2)+'\n');
 console.log(results.checks.length+' browser assertions passed; 6 theme/viewport axe audits clean.');
}finally{
 fs.writeFileSync(output+'/browser-checks.json',JSON.stringify(results,null,2)+'\n');
 await browser.close();
}
