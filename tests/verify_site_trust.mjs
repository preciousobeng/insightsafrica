import {createRequire} from 'node:module';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const puppeteer=require(process.env.MAINTENANCE_PUPPETEER || 'puppeteer-core');
const base='http://127.0.0.1:8774';
const browser=await puppeteer.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
const results=[];
fs.mkdirSync('node_modules/maintenance-evidence',{recursive:true});
try{
 for(const width of [375,800,986,987,1024,1100,1280,1440]){
  for(const theme of ['dark','light']){
   const page=await browser.newPage();await page.setViewport({width,height:1000});
   await page.evaluateOnNewDocument(theme=>localStorage.setItem('ia-theme',theme),theme);
   const errors=[];page.on('pageerror',error=>errors.push(error.message));
   await page.setRequestInterception(true);
   page.on('request',request=>{
    const url=new URL(request.url());
    if(url.origin===base)return request.continue();
    return request.respond({status:204,body:''});
   });
   await page.goto(base,{waitUntil:'networkidle0'});await page.evaluate(()=>document.fonts.ready);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width+' '+theme);
   const mobile=width<=986;
   assert.equal(await page.$eval('.nav-hamburger',e=>getComputedStyle(e).display!=='none'),mobile);
   if(mobile){
    await page.click('.nav-hamburger');
    assert(await page.$eval('.nav-mobile',e=>e.classList.contains('open')));
    assert(await page.$eval('.nav-mobile a[href*="monitor."]',e=>e.textContent.includes('Intelligence')));
    await page.click('.nav-hamburger');
   }else{
    assert(await page.$$eval('#nav a,#nav .theme-toggle',elements=>{const rects=elements.filter(e=>getComputedStyle(e).display!=='none'&&e.getBoundingClientRect().width>0).map(e=>e.getBoundingClientRect()).sort((a,b)=>a.left-b.left);return rects.every((r,i)=>r.left>=0&&r.right<=innerWidth&&(!i||r.left>=rects[i-1].right));}));
   }
   assert(await page.$('a[href="/privacy.html"]'));
   await page.screenshot({path:'node_modules/maintenance-evidence/current-'+width+'-'+theme+'.png',fullPage:true});
   assert.deepEqual(errors,[]);
   results.push({width,theme,errors,overflow:false,mobileMenu:mobile});
   await page.close();
  }
 }
 for(const path of ['/login.html','/ghana/hub.html']){
  const page=await browser.newPage();const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const calls=[];
  await page.setRequestInterception(true);
  page.on('request',request=>{
   const url=new URL(request.url());
   if(url.origin===base)return request.continue();
   calls.push(url.hostname);
   return request.respond({status:503,body:'Provider requests disabled in QA'});
  });
  await page.goto(base+path,{waitUntil:'networkidle0'});
  assert.equal(await page.evaluate(()=>typeof window.supabase?.createClient),'function');
  assert(await page.$('a[href="/privacy.html"]'));
  assert.deepEqual(errors,[]);
  assert(!calls.some(host=>host.endsWith('.supabase.co')),'Unexpected live auth request');
  results.push({path,realSelfHostedSdkLoaded:true,errors,liveAuthRequests:0});
  await page.close();
 }
 for(const country of ['ghana','nigeria','ivorycoast','senegal','capeverde','southafrica']){
  for(const status of [200,503]){
   const page=await browser.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
   await page.setRequestInterception(true);
   page.on('request',request=>{
    const url=new URL(request.url());
    if(url.origin===base && url.pathname.startsWith('/api/'))return request.respond({status,contentType:'application/json',body:JSON.stringify(status===200?[]:{detail:'Fixture unavailable'})});
    if(url.origin===base)return request.continue();
    return request.respond({status:204,body:''});
   });
   await page.goto(base+'/'+country+'/hub.html',{waitUntil:'networkidle0'});
   await page.waitForFunction(()=>document.querySelectorAll('.kpi-loading').length===0);
   assert.deepEqual(errors,[]);
   results.push({country,status,emptyOrUnavailableHandled:true,errors});
   await page.close();
  }
 }
 fs.writeFileSync('node_modules/maintenance-evidence/site-trust-browser.json',JSON.stringify(results,null,2));
 console.log('PASS: 16 responsive/theme renders, actual pinned SDK, 12 empty/error hub cases; zero uncaught errors or live auth requests.');
}finally{await browser.close();}
