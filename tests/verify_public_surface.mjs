import {createRequire} from 'node:module';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const puppeteer=require(process.env.MAINTENANCE_PUPPETEER || 'puppeteer-core');
const base='http://127.0.0.1:8773';
const cached='node_modules/maintenance-assets/';
const browser=await puppeteer.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
const results=[];
try {
 for(const country of ['ghana','nigeria','ivorycoast','senegal','capeverde','southafrica']){
  const page=await browser.newPage();
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.setRequestInterception(true);
  page.on('request',request=>{
   const url=new URL(request.url());
   if(url.origin===base && url.pathname.endsWith('/flood/layers')){
    const stats=Object.fromEntries(['regions','districts','states','lgas','departments','islands','provinces'].map(level=>[level,{'Example':{mean:50,min:0,max:100},'Example|Parent':{mean:50,min:0,max:100}}]));
    return request.respond({status:200,contentType:'application/json',body:JSON.stringify([{year:2026,month:9,label:'Synthetic fixture September 2026',png:'fixture.png',leaflet_bounds:[[0,0],[1,1]],rainfall_mm:{min:0,max:100,mean:50,colorscale_cap:100},zonal_stats:stats}])});
   }
   if(url.origin===base && url.pathname.includes('/boundaries/'))return request.respond({status:200,contentType:'application/json',body:JSON.stringify({type:'FeatureCollection',features:[{type:'Feature',properties:{name:'Example',region:'Parent'},geometry:{type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}}]})});
   if(url.origin===base && url.pathname.endsWith('/fixture.png'))return request.respond({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
   if(url.origin===base)return request.continue();
   if(url.href.includes('leaflet.js'))return request.respond({status:200,contentType:'application/javascript',body:fs.readFileSync(cached+'leaflet.js')});
   if(url.href.includes('leaflet.css'))return request.respond({status:200,contentType:'text/css',body:fs.readFileSync(cached+'leaflet.css')});
   if(url.href.includes('chart.umd'))return request.respond({status:200,contentType:'application/javascript',body:fs.readFileSync(cached+'chart.js')});
   if(url.href.includes('supabase-js'))return request.respond({status:200,contentType:'application/javascript',body:fs.readFileSync(cached+'supabase.js')});
   if(request.resourceType()==='image')return request.respond({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
   if(request.resourceType()==='stylesheet')return request.respond({status:200,contentType:'text/css',body:''});
   return request.respond({status:204,body:''});
  });
  await page.goto(base+'/'+country+'/flood/',{waitUntil:'networkidle0'});
  await page.waitForFunction(()=>document.querySelectorAll('path.leaflet-interactive').length>0,{timeout:10000});
  const polygons=await page.$$eval('path.leaflet-interactive',elements=>elements.length);
  const downloads=await page.$$eval('a[download]',elements=>elements.map(e=>e.href));
  assert(!downloads.some(url=>url.endsWith('.geojson')||url.includes('/boundaries/')));
  assert.equal(errors.length,0,errors.join('\n'));
  assert(await page.$eval('#layer-label',e=>e.textContent.includes('Synthetic fixture')));
  results.push({country,polygons,errors,bulkBoundaryDownloadLinks:0});
  await page.close();
 }
 fs.mkdirSync('node_modules/maintenance-evidence',{recursive:true});
 fs.writeFileSync('node_modules/maintenance-evidence/public-surface-browser.json',JSON.stringify(results,null,2));
 console.log(JSON.stringify(results,null,2));
}finally{await browser.close();}
