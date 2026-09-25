// Real Chromium layout and interaction checks against the local desktop server.
const {chromium}=require(process.env.NEXO_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert');
const {spawn}=require('child_process');
const root=path.resolve(__dirname,'..'),directory=fs.mkdtempSync(path.join(os.tmpdir(),'nexo-browser-'));
const child=spawn(process.env.NEXO_PYTHON||'python',['-m','nexo7.desktop','--no-open','--data-dir',directory],{cwd:root,stdio:'ignore'});
const output=path.join(root,'reports','browser');fs.mkdirSync(output,{recursive:true});
let browser;
(async()=>{try{
 const deadline=Date.now()+45000;while(!fs.existsSync(path.join(directory,'access.json'))){if(Date.now()>deadline||child.exitCode!==null)throw Error('Desktop failed to start');await new Promise(r=>setTimeout(r,100));}
 const access=JSON.parse(fs.readFileSync(path.join(directory,'access.json'),'utf8'));
 browser=await chromium.launch({headless:true,executablePath:process.env.NEXO_CHROME||undefined,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1366,height:768}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(access.url);await page.locator('#try-demo').click();
 await page.locator('#composer').waitFor({state:'visible'});
 assert.equal(await page.locator('#chat-options').getAttribute('open'),null);
 assert.equal(await page.locator('#web-controls').isVisible(),false);
 const sendBox=await page.locator('#send').boundingBox();assert(sendBox.y+sendBox.height<=768,'Send button must fit a laptop screen without scrolling');
 await page.screenshot({path:path.join(output,'chat-desktop.png'),fullPage:true});
 await page.locator('#theme-toggle').click();await page.screenshot({path:path.join(output,'chat-dark.png'),fullPage:true});await page.locator('#theme-toggle').click();
 await page.locator('#prompt').fill('/calc 12*12');await page.locator('#prompt').press('Enter');await page.getByText('144',{exact:true}).waitFor();
 await page.locator('#prompt').fill('Draw me a chicken');await page.locator('#prompt').press('Enter');
 await page.locator('.chat-files img').waitFor();assert.equal(await page.locator('.chat-files a[download="drawing.png"]').count(),1);
 await page.locator('.assistant').last().getByRole('button',{name:'Download Word',exact:true}).click();
 await page.locator('.chat-files a[download="Nexo-document.docx"]').waitFor();
 await page.screenshot({path:path.join(output,'chat-drawing.png'),fullPage:true});
 await page.locator('#open-scenario').click();await page.locator('#scenario-form button').click();await page.getByText('Horizontal distance (m): 10.1937',{exact:true}).waitFor();
 await page.screenshot({path:path.join(output,'scenario-calculator.png'),fullPage:true});
 await page.locator('#workspace-tab').click();assert.equal(await page.locator('#creative-spec').isVisible(),false);
 await page.locator('#creative-render').click();await page.locator('#creative-output img').waitFor();
 await page.screenshot({path:path.join(output,'create-desktop.png'),fullPage:true});
 await page.locator('#creative-kind').selectOption('music');await page.locator('#music-tempo').fill('120');await page.locator('#music-tempo').press('Tab');
 await page.locator('#creative-render').click();await page.locator('#creative-output audio').waitFor();
 assert.equal(await page.locator('a[download="music.mid"]').count(),1);
 for(const width of [1366,390]){
  await page.setViewportSize({width,height:850});
  for(const [id,name] of [['chat-tab','chat'],['workspace-tab','create'],['setup-tab','settings']]){
   await page.locator('#'+id).click();await page.evaluate(()=>window.scrollTo(0,0));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),`Horizontal overflow: ${name} at ${width}`);
   if(width===390)await page.screenshot({path:path.join(output,name+'-mobile.png'),fullPage:true});
  }
 }
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({passed:true,checks:['desktop and mobile layout without horizontal overflow','collapsed options','theme switch','keyboard send','what-if calculation','PNG preview','WAV/MIDI controls','no browser JavaScript errors']},null,2));
 console.log('Chromium UI checks passed');
}finally{if(browser)await browser.close();child.kill();await new Promise(r=>child.exitCode!==null?r():child.once('exit',r));fs.rmSync(directory,{recursive:true,force:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
