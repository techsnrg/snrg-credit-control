/* Isolated navigation/layout journeys. Native editor/upload flows are verified on staging. */
const {chromium}=require('@playwright/test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined,headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const assets=path.resolve(__dirname,'../snrg_credit_control/public/dist');
  await page.route('http://workspace.test/**',route=>{const ext=route.request().url().endsWith('.js')?'js':'css';return route.fulfill({contentType:ext==='js'?'application/javascript':'text/css',body:fs.readFileSync(path.join(assets,'customer_workspace.'+ext),'utf8')})});
  await page.setContent('<div class="body-sidebar-container">Desk</div><div id="page-customer-workspace" class="snrg-customer-workspace-page"><div class="page-head">Teamspace</div><div id="app"></div></div>');
  await page.addStyleTag({content:':root{--fg-color:#fff;--bg-color:#fafafa;--control-bg:#f5f5f5;--text-color:#222;--text-muted:#666;--border-color:#ddd}[data-theme=dark]{--fg-color:#171717;--control-bg:#272727;--text-color:#eee;--text-muted:#aaa;--border-color:#444}'});
  await page.evaluate(()=>{
   document.documentElement.dataset.theme='light';
   const customer={name:'C1',customer_name:'HBR',party_name:'HBR',party_type:'Customer',mobile_number:'9876543210',territory:'Odisha',location:'Odisha',customer_group:'Dealer',group_name:'Dealer'};
   const supplier={name:'S1',supplier_name:'ABC Supplies',party_name:'ABC Supplies',party_type:'Supplier',mobile_number:'',country:'India',location:'India',supplier_group:'Distributor',group_name:'Distributor'};
   const task={name:'CA-1',subject:'Arrange pickup',customer:'C1',customer_name:'HBR',party:'C1',party_name:'HBR',party_type:'Customer',due_date:'2026-11-20',assigned_to:'me@example.test',owner:'me@example.test',status:'Open',modified:'v1'};
   window.frappe={datetime:{str_to_user:x=>x,now_datetime:()=> '2026-11-19 10:00:00'},set_route:()=>{},call:async({method,args})=>{
    const m=method.split('.').pop();let message;
    if(m==='bootstrap')message={user:'me@example.test',is_manager:true,today:'2026-11-19',employees:[{name:'EMP-1',employee_name:'Nikhil',user_id:'me@example.test',can_notify:true},{name:'EMP-2',employee_name:'Priya',user_id:'priya@example.test',can_notify:true}],can_ar:true,can_ar_detail:true,can_ap:true,can_ap_detail:true,can_transactions:true,companies:[{name:'Test Company'}],ap_companies:[{name:'Test Company'}],territories:['Odisha'],customer_groups:['Dealer'],countries:['India'],supplier_groups:['Distributor']};
    if(m==='actions'||m==='personal_agenda')message=[task];
    if(m==='customer_directory'||m==='supplier_directory'){window.directoryArgs=args;message={rows:[m==='supplier_directory'?supplier:customer],has_more:false}}
    if(m==='timeline'){window.timelineArgs=args;message={events:[{kind:'plan',name:'plan:CA-1',summary:'Arrange pickup',action:task,interaction_on:'2026-11-20 10:00:00'},...(args.include_transactions?[{kind:'transaction',name:'invoice:INV-1',summary:'Sales Invoice',document_type:'Sales Invoice',document_name:'INV-1',status:'Unpaid',docstatus:1,amount:20000,currency:'INR',interaction_on:'2026-11-19 09:00:00',allocations:[]}]:[])],has_more:false}}
    if(m==='customer_ar'||m==='supplier_ap')message={rows:[{...(m==='supplier_ap'?supplier:customer),outstanding:1000,due_now:600,age_0_30:600,age_91_120:0,age_over_120:0}],totals:{outstanding:1000,due_now:600,not_yet_due:400,advance:0},count:1,has_more:false,currency:'INR',report_date:args.report_date,due_note:'Company currency'};
    if(m.endsWith('_invoices'))message={rows:[],has_more:false};
    if(m==='create_action'){window.createdTask=args.payload;message={name:'CA-2'}}
    if(m==='visibility_settings')message={restrict_ar:0,restrict_ap:0,restrict_transactions:0,access:[]};
    return {message};
   }};
  });
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addStyleTag({url:'http://workspace.test/app.css'});await page.addScriptTag({url:'http://workspace.test/app.js'});
  await page.evaluate(()=>window.snrgCustomerWorkspace.mount(document.getElementById('app')));
  await page.getByRole('heading',{name:'My day',exact:true}).waitFor();
  assert.equal(await page.locator('.body-sidebar-container').isVisible(),false);
  assert.equal(await page.locator('.page-head').isVisible(),false);
  assert.equal(await page.locator('main .heading>.primary').innerText(),'New follow-up');
  await page.evaluate(()=>document.documentElement.dataset.theme='dark');assert.equal(await page.locator('#cw').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(23, 23, 23)');
  await page.evaluate(()=>document.documentElement.dataset.theme='light');
  await page.getByRole('button',{name:'All customers',exact:true}).click();
  await page.getByRole('heading',{name:'Customers',exact:true}).waitFor();assert.equal(await page.locator('main .heading>.primary').count(),0);
  assert.equal(await page.getByRole('link',{name:'9876543210',exact:true}).getAttribute('href'),'tel:9876543210');
  await page.locator('.directory-row .customer-identity').click();
  await page.getByRole('heading',{name:'HBR',exact:true}).waitFor();
  await page.getByRole('checkbox',{name:'Show transactions',exact:true}).check();await page.getByText('INV-1 ↗',{exact:true}).waitFor();
  await page.getByRole('checkbox',{name:'Show transactions',exact:true}).uncheck();await page.waitForFunction(()=>window.timelineArgs.include_transactions===0);
  await page.getByText('INV-1 ↗',{exact:true}).waitFor({state:'hidden'});assert.equal(await page.locator('.planned-event').count(),1);
  await page.getByRole('button',{name:'All suppliers',exact:true}).click();await page.getByRole('heading',{name:'Suppliers',exact:true}).waitFor();
  await page.locator('.directory-row .customer-identity').click();await page.getByRole('heading',{name:'ABC Supplies',exact:true}).waitFor();
  await page.getByRole('button',{name:'Team follow-ups',exact:true}).click();await page.getByRole('button',{name:'Assign task',exact:true}).click();
  await page.getByRole('combobox',{name:'Relationship type',exact:true}).selectOption('Supplier');await page.getByRole('combobox',{name:'Supplier',exact:true}).fill('ABC');
  await page.getByRole('option',{name:'ABC Supplies S1 · India',exact:true}).click();
  await page.getByRole('textbox',{name:'What needs to happen?',exact:true}).fill('Confirm delivery');await page.getByRole('button',{name:'Create follow-up',exact:true}).click();
  await page.waitForFunction(()=>window.createdTask?.supplier==='S1');assert.equal((await page.evaluate(()=>window.createdTask)).customer,null);
  await page.getByRole('button',{name:'Visibility settings',exact:true}).click();await page.getByRole('checkbox',{name:'Limit Customer AR to selected employees',exact:true}).check();await page.getByRole('textbox',{name:'Find employee',exact:true}).fill('Priya');await page.getByText('priya@example.test',{exact:true}).waitFor();await page.getByRole('button',{name:'Cancel',exact:true}).click();
  const desk=page.getByRole('link',{name:'Open ERPNext Desk in new tab',exact:true});assert.equal(await desk.getAttribute('href'),'/desk');assert.equal(await desk.getAttribute('target'),'_blank');
  await page.getByRole('button',{name:'Customer AR',exact:true}).click();await page.getByRole('button',{name:'Details',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Apply filters',exact:true}).count(),0);assert.equal(await page.getByRole('combobox',{name:'Balance',exact:true}).count(),0);
  assert.deepEqual(errors,[]);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  console.log('PASS: contextual tasks, supplier/customer navigation, unified timeline toggle, plans, visibility controls, themes and responsive layout.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
