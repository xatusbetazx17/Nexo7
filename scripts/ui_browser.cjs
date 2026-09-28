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
 browser=await chromium.launch({headless:true,executablePath:process.env.NEXO_CHROME||undefined,args:['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 const page=await browser.newPage({viewport:{width:1366,height:768}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(access.url);await page.locator('#navi-onboarding').waitFor({state:'visible'});
 const introButton=await page.locator('#onboarding-form button').first().boundingBox();assert(introButton.y+introButton.height<=768,'First-run action must fit without scrolling');await page.screenshot({path:path.join(output,'onboarding.png'),fullPage:true});
 await page.locator('#onboarding-name').fill('Luna');await page.locator('#onboarding-user').fill('Test user');await page.locator('#onboarding-remember').check();await page.locator('#onboarding-form button').first().click();await page.locator('#navi-onboarding').waitFor({state:'hidden'});assert((await page.locator('#navi-welcome').innerText()).includes('Luna'));
 await page.locator('#try-demo').click();
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
 await page.locator('#workspace-tab').click();await require('./media_browser_checks.cjs')(page);assert.equal(await page.locator('#creative-spec').isVisible(),false);
 await page.locator('#creative-render').click();await page.locator('#creative-output img').waitFor();
 await page.screenshot({path:path.join(output,'create-desktop.png'),fullPage:true});
 await page.locator('#creative-kind').selectOption('music');await page.locator('#music-tempo').fill('120');await page.locator('#music-tempo').press('Tab');
 await page.locator('#creative-render').click();await page.locator('#creative-output audio').waitFor();
 assert.equal(await page.locator('a[download="music.mid"]').count(),1);
 await page.locator('#navi-tab').click();await page.locator('#navi-view').waitFor({state:'visible'});
 assert.equal(await page.locator('#navi-avatar').isChecked(),false);
 await page.locator('#navi-scheduler').check();await page.locator('#navi-reminder-text').fill('Browser reminder');await page.locator('#navi-reminder-time').fill('2026-01-01T10:00');await page.locator('#navi-reminder-form button').click();await page.locator('#navi-reminders').getByText(/Browser reminder/).waitFor();
 await page.locator('#navi-chips').locator('..').evaluate(e=>e.open=true);
 await page.locator('#navi-chip-run').click();await page.locator('#navi-chip-result').filter({hasText:'2.5'}).waitFor();

 await page.locator('#episodes-panel summary').click();await page.locator('#episode-what').fill('Finished the violet project');await page.locator('#episode-people').fill('Ana');await page.locator('#episode-form button').first().click();await page.locator('#episode-list').getByText('Finished the violet project',{exact:true}).waitFor();
 await page.locator('#catalog-panel summary').click();await page.locator('#catalog-refresh').click();await page.locator('#catalog-list').getByText('study-math',{exact:true}).waitFor();
 const vaultParent=page.locator('#navi-vault-unlock').locator('..');await vaultParent.evaluate(e=>e.open=true);await page.locator('#navi-vault-phrase').fill('a browser test vault passphrase');await page.locator('#navi-vault-unlock').click();await page.locator('#navi-vault-status').filter({hasText:/Unlocked|unlocked/}).waitFor();
 await page.locator('#mail-panel summary').click();await page.locator('#mail-mode').selectOption('draft');await page.locator('#mail-mode-save').click();await page.locator('#mail-status').filter({hasText:'access level saved'}).waitFor();await page.locator('#mail-sender').fill('owner@example.com');await page.locator('#mail-to').fill('recipient@example.com');await page.locator('#mail-subject').fill('Local draft');await page.locator('#mail-text').fill('Not sent to any real account.');await page.locator('#mail-form button').first().click();await page.locator('#mail-list').getByText('Local draft',{exact:true}).waitFor();
 await page.locator('#navi-vault-lock').click();assert.equal(await page.locator('#mail-list').innerText(),'');
 await page.screenshot({path:path.join(output,'navi-desktop.png'),fullPage:true});
 await page.locator('#navi-voice').check();await page.locator('#chat-tab').click();
 let recordingChecked=false;
 await page.route('**/api/navi/voice/transcribe',async route=>{const body=route.request().postDataJSON(),wav=Buffer.from(body.data,'base64');assert.equal(wav.toString('ascii',0,4),'RIFF');assert.equal(wav.readUInt32LE(24),16000);assert.equal(wav.readUInt16LE(22),1);assert(wav.length>44&&wav.length<=1050000);recordingChecked=true;await route.fulfill({json:{text:'Reviewed voice transcript',local:true}});});
 const beforeVoice=await page.locator('.message').count();
 await page.locator('#navi-record').click();await page.locator('#navi-record-status').filter({hasText:'Listening'}).waitFor();await page.waitForTimeout(500);await page.locator('#navi-record').click();await page.waitForFunction(()=>document.querySelector('#prompt').value==='Reviewed voice transcript');assert(recordingChecked);assert.equal(await page.locator('.message').count(),beforeVoice,'Recording must not auto-send');
 await page.unroute('**/api/navi/voice/transcribe');await page.locator('#prompt').fill('');

 await page.locator('#setup-tab').click();
 // Telegram discovery survives background status refresh; owner selects the chat.
 await page.route('**/api/telegram',route=>route.fulfill({json:{phase:'off',received:0,ignored:0,replied:0}}));
 await page.route('**/api/telegram/chats',route=>route.fulfill({json:{chats:[{id:24680,type:'private'}],notice:'Choose your conversation.'}}));
 let telegramStarted=false;
 await page.route('**/api/telegram/start',route=>{const b=route.request().postDataJSON();assert.deepEqual(b.chat_ids,[24680]);assert.equal(b.consent,true);telegramStarted=true;return route.fulfill({json:{phase:'starting'}});});
 await page.getByText('Optional Telegram access',{exact:true}).click();
 await page.locator('#telegram-token').fill('123:'+'x'.repeat(25));await page.locator('#telegram-consent').check();await page.locator('#telegram-discover').click();
 await page.getByRole('button',{name:'Allow 24680 (private)',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#telegram-health').textContent.includes('Received:'));
 assert((await page.locator('#telegram-status').innerText()).includes('Chat selected'));
 await page.locator('#telegram-form button[type=submit]').click();await page.locator('#telegram-status').filter({hasText:'The token field was cleared'}).waitFor();assert(telegramStarted);
 assert.equal(await page.locator('#telegram-token').inputValue(),'');assert(await page.locator('#telegram-consent').isChecked());
 await page.getByText('Optional Telegram access',{exact:true}).click();
 await page.locator('#trust-panel summary').click();
 await page.locator('#navi-id').filter({hasText:'nexo:'}).waitFor();
 await page.getByRole('checkbox',{name:'Calculations and date tools',exact:true}).uncheck();
 await page.locator('#trust-status').filter({hasText:'disabled'}).waitFor();
 await page.getByRole('checkbox',{name:'Calculations and date tools',exact:true}).check();
 await page.locator('#trust-status').filter({hasText:'enabled'}).waitFor();
 await page.locator('#audit-verify').click();
 await page.locator('#trust-status').filter({hasText:'Verified'}).waitFor();
 await page.screenshot({path:path.join(output,'trust-desktop.png'),fullPage:true});
 for(const width of [1366,390]){
  await page.setViewportSize({width,height:850});
  for(const [id,name] of [['chat-tab','chat'],['workspace-tab','create'],['setup-tab','settings']]){
   await page.locator('#'+id).click();await page.evaluate(()=>window.scrollTo(0,0));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),`Horizontal overflow: ${name} at ${width}`);
   if(width===390)await page.screenshot({path:path.join(output,name+'-mobile.png'),fullPage:true});
  }
 }
 await page.setViewportSize({width:1366,height:850});await page.locator('#setup-tab').click();
 await page.locator('#accent-preset').selectOption('#7251b5');assert.equal(await page.evaluate(()=>document.documentElement.style.getPropertyValue('--accent')),'#7251b5');
 await page.screenshot({path:path.join(output,'personal-colors.png'),fullPage:true});
 await page.locator('#companion-consent').check();await page.locator('#companion-start').click();await page.locator('#companion-status').filter({hasText:'Browser companion is on'}).waitFor();
 const companionLink=await page.locator('#companion-links a').first().getAttribute('href');const companionPage=await browser.newPage({viewport:{width:390,height:844}});companionPage.on('pageerror',e=>errors.push(e.message));await companionPage.goto(companionLink);
 await companionPage.getByText('Appearance and connection',{exact:true}).click();await companionPage.locator('#color').selectOption('rose');await companionPage.locator('#face').selectOption('🐱');assert.equal(await companionPage.locator('#avatar').innerText(),'🐱');
 assert(await companionPage.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1));await companionPage.screenshot({path:path.join(output,'companion-phone.png'),fullPage:true});await companionPage.close();
 await page.locator('#companion-stop').click();await page.locator('#companion-status').filter({hasText:'off'}).waitFor();
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({passed:true,checks:['named onboarding and persistent persona','reviewed episodic memory','offline chip discovery','encrypted local draft without sending','desktop and mobile layout without horizontal overflow','collapsed options','theme switch','keyboard send','what-if calculation','PNG preview','WAV/MIDI controls','real microphone capture produces a reviewed 16 kHz WAV without auto-send','Navi reminders and signed math chip','no browser JavaScript errors']},null,2));
 console.log('Chromium UI checks passed');
}finally{if(browser)await browser.close();child.kill();await new Promise(r=>child.exitCode!==null?r():child.once('exit',r));fs.rmSync(directory,{recursive:true,force:true});}})().catch(e=>{console.error(e);process.exitCode=1;});
