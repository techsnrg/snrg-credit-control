/* Isolated UI journeys. Backend report permissions are tested in test_integration.py. */
const {chromium}=require('@playwright/test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const assetRoot=path.resolve(__dirname,'../snrg_credit_control/public/dist');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined,headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.route('http://workspace.test/**',route=>{
  const file=route.request().url().endsWith('app.js')?'customer_workspace.js':'customer_workspace.css';
  return route.fulfill({contentType:file.endsWith('.js')?'application/javascript':'text/css',body:fs.readFileSync(path.join(assetRoot,file),'utf8')});
 });
 await page.setContent('<div class="body-sidebar-container">ERPNext navigation</div><div id="page-customer-workspace" class="snrg-customer-workspace-page"><div class="page-head">Customer Workspace</div><div id="app"></div></div>');
 await page.addStyleTag({content:':root{--fg-color:#ffffff;--bg-color:#fafafa;--control-bg:#f5f5f5;--text-color:#222222;--text-muted:#666666;--border-color:#dddddd;--dark-border-color:#bbbbbb;--subtle-fg:#eeeeee;--modal-bg:#ffffff;--popover-bg:#ffffff;--alert-text-danger:#b00020}[data-theme=dark]{--fg-color:#171717;--control-bg:#272727;--text-color:#eeeeee;--text-muted:#aaaaaa;--border-color:#444444;--modal-bg:#171717;--popover-bg:#171717}'});
 await page.emulateMedia({colorScheme:'dark'});
 await page.evaluate(()=>{
  document.documentElement.dataset.theme='light';
  const customer={name:'C1',customer_name:'HBR',mobile_number:'9876543210',territory:'Odisha',customer_group:'Dealer'};
  window.frappe={datetime:{str_to_user:x=>x,now_datetime:()=> '2026-11-19 10:00:00'},set_route:()=>{},call:async({method,args})=>{
   const m=method.split('.').pop();let message;
   const employees=[{name:'EMP-1',employee_name:'Nikhil Goel',user_id:'me@example.test',can_notify:true},{name:'EMP-2',employee_name:'Priya Sharma',department:'Supply Chain',user_id:'priya@example.test',can_notify:true},{name:'EMP-3',employee_name:'No Login Employee',can_notify:false}];
   if(m==='bootstrap')message={user:'me@example.test',is_manager:true,today:'2026-11-19',employees,can_ar:true,can_ar_detail:true,companies:[{name:'SNRG Test',default_currency:'INR'}],territories:['Odisha'],customer_groups:['Dealer']};
   if(m==='actions'||m==='personal_agenda')message=[{name:'CA-1',subject:'Arrange pickup',customer:'C1',customer_name:'HBR',due_date:'2026-11-19',assigned_to:'me@example.test',owner:'me@example.test',status:'Open',modified:'v1'}];
   if(m==='customers')message=[customer];
   if(m==='customer_directory'){window.directoryArgs=args;message={rows:[customer],has_more:false,start:0};}
   if(m==='history')message={interactions:[],calls:[]};
   if(m==='log_interaction'){window.saved=args.payload;message={name:'CI-1',actions:[]};}
   if(m==='customer_ar')message={rows:[{...customer,outstanding:1000,due_now:600}],totals:{outstanding:1000,due_now:600,not_yet_due:400,advance:0},count:1,has_more:false,currency:'INR',report_date:'2026-11-19',due_note:'Company currency'};
   if(m==='customer_ar_invoices')message={rows:[{voucher_no:'INV-001',voucher_type:'Sales Invoice',posting_date:'2026-11-01',due_date:'2026-11-15',outstanding:600,age_days:18,age_basis:'posting_date'}],count:1,has_more:false};
   return {message};
  }};
 });
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addStyleTag({url:'http://workspace.test/app.css'});
 await page.addScriptTag({url:'http://workspace.test/app.js'});
 await page.evaluate(()=>window.snrgCustomerWorkspace.mount(document.getElementById('app')));
 await page.getByRole('heading',{name:'My day',exact:true}).waitFor();
 assert.equal(await page.locator('.body-sidebar-container').isVisible(),false);
 assert.equal(await page.locator('.page-head').isVisible(),false);
 assert.equal(await page.locator('#cw').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(255, 255, 255)');
 await page.evaluate(()=>document.documentElement.dataset.theme='dark');
 assert.equal(await page.locator('#cw').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(23, 23, 23)');
 await page.evaluate(()=>document.documentElement.dataset.theme='light');
 await page.getByRole('button',{name:'Log interaction',exact:true}).click();
 await page.locator('select').filter({has:page.locator('option[value="C1"]')}).selectOption('C1');
 await page.getByRole('textbox',{name:'Discussion summary'}).fill('Please coordinate @Pri');
 await page.locator('#cw-mentions').getByRole('option',{name:/Priya Sharma/}).waitFor();
 await page.getByRole('textbox',{name:'Discussion summary'}).press('Enter');
 await page.getByRole('button',{name:'Save conversation',exact:true}).click();
 await page.getByRole('status').waitFor();
 assert.deepEqual((await page.evaluate(()=>window.saved)).mentions,['EMP-2']);
 await page.getByRole('button',{name:'All customers',exact:true}).click();
 await page.getByRole('heading',{name:'Customers',exact:true}).waitFor();
 await page.locator('.directory-view .customer-identity').waitFor();
 assert.equal(await page.getByRole('link',{name:'9876543210',exact:true}).getAttribute('href'),'tel:9876543210');
 await page.getByLabel('Territory',{exact:true}).selectOption('Odisha');
 await page.waitForFunction(()=>window.directoryArgs.territory==='Odisha');
 await page.locator('.directory-view .customer-identity').click();
 await page.getByRole('heading',{name:'HBR',exact:true}).waitFor();
 await page.getByRole('button',{name:'Open follow-ups',exact:true}).click();
 await page.getByRole('button',{name:'Arrange pickup',exact:true}).waitFor();
 await page.getByRole('button',{name:'Receivables',exact:true}).click();
 await page.getByRole('button',{name:'INV-001 Sales Invoice',exact:true}).waitFor();await page.getByText('18 days',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Customer AR',exact:true}).click();
 await page.getByRole('heading',{name:'Customer AR',exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Apply filters',exact:true}).count(),0);
 assert.equal(await page.getByRole('combobox',{name:'Balance',exact:true}).count(),0);
 await page.getByRole('button',{name:'Details',exact:true}).waitFor();
 await page.locator('.ar-interaction').click();
 assert.equal(await page.getByRole('dialog').locator('select').filter({has:page.locator('option[value="C1"]')}).inputValue(),'C1');
 await page.getByRole('textbox',{name:'Discussion summary'}).fill('Payment follow-up from AR');
 await page.getByRole('button',{name:'Save conversation',exact:true}).click();
 await page.getByRole('heading',{name:'Customer AR',exact:true}).waitFor();
 assert.equal((await page.evaluate(()=>window.saved)).customer,'C1');
 assert.deepEqual(errors,[]);
 if(process.env.CW_SCREENSHOT_DIR)await page.locator('#cw').screenshot({path:process.env.CW_SCREENSHOT_DIR+'/customer-ar.png',animations:'disabled'});
 await page.getByRole('button',{name:'All customers',exact:true}).click();
 await page.locator('.directory-view .customer-identity').waitFor();
 if(process.env.CW_SCREENSHOT_DIR)await page.locator('#cw').screenshot({path:process.env.CW_SCREENSHOT_DIR+'/customer-directory.png',animations:'disabled'});
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.evaluate(()=>document.getElementById('page-customer-workspace').style.display='none');
 assert.equal(await page.locator('.body-sidebar-container').isVisible(),true);
 console.log('PASS: theme switching, scoped sidebar/header removal, mentions, customer directory/mobile/filter, customer AR/documents and mobile layout.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
