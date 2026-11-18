import { build } from 'esbuild';
import { createHash } from 'node:crypto';
import { readFile, writeFile, readdir, rm } from 'node:fs/promises';
const output='snrg_credit_control/public/dist';
await build({entryPoints:['snrg_credit_control/public/customer_workspace/app.js'],outfile:output+'/customer_workspace.js',bundle:true,minify:true,format:'iife',globalName:'snrgCustomerWorkspace',alias:{vue:'vue/dist/vue.esm-bundler.js'},define:{'process.env.NODE_ENV':'"production"',__VUE_OPTIONS_API__:'true',__VUE_PROD_DEVTOOLS__:'false',__VUE_PROD_HYDRATION_MISMATCH_DETAILS__:'false'}});
// Content-addressed filenames bypass Desk's asset cache and the browser HTTP cache.
for(const name of await readdir(output)){
  if(/^customer_workspace\.[a-f0-9]{12}\.(js|css)$/.test(name))await rm(output+'/'+name,{force:true});
}
const assets={};
for(const extension of ['js','css']){
  const content=await readFile(output+'/customer_workspace.'+extension);
  const hash=createHash('sha256').update(content).digest('hex').slice(0,12);
  const filename=`customer_workspace.${hash}.${extension}`;
  await writeFile(output+'/'+filename,content);
  assets[extension]='/assets/snrg_credit_control/dist/'+filename;
}
await writeFile('snrg_credit_control/snrg_credit_control/page/customer_workspace/customer_workspace.js',`frappe.pages["customer-workspace"].on_page_load = function(wrapper) {
  wrapper.classList.add("snrg-customer-workspace-page");
  const page = frappe.ui.make_app_page({parent: wrapper, title: __("Teamspace"), single_column: true});
  frappe.require(["${assets.css}", "${assets.js}"], () => window.snrgCustomerWorkspace.mount(page.main[0]));
};
`);
console.log('Workspace assets:', assets);
