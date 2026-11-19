// Per-mount, memory-only reuse. Never persists finance data across logins/devices.
export function financeRequests(request, {ttl=15000, now=()=>Date.now()}={}) {
 const entries=new Map();let generation=0;
 const stable=value=>value&&typeof value==='object'&&!Array.isArray(value)?Object.fromEntries(Object.keys(value).sort().map(key=>[key,stable(value[key])])):Array.isArray(value)?value.map(stable):value;
 function clear(){generation++;entries.clear()}
 async function load(method,args,user){
  const key=JSON.stringify([user,method,stable(args)]),cached=entries.get(key);
  if(cached&&(cached.pending||now()-cached.at<ttl))return cached.pending||cached.data;
  const epoch=generation,entry={};entries.delete(key);entries.set(key,entry);
  const pending=Promise.resolve().then(()=>request(method,args));entry.pending=pending;
  try{const data=await pending;if(epoch===generation&&entries.get(key)===entry){entry.data=data;entry.at=now();delete entry.pending;while(entries.size>20)entries.delete(entries.keys().next().value)}return data}
  catch(error){if(entries.get(key)===entry)entries.delete(key);throw error}
 }
 return {load,clear};
}
