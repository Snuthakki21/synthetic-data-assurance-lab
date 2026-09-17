// Presentation helpers: every template chooses its own information hierarchy.
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const human = value => String(value ?? '').replaceAll('_',' ');
export const numeric = (value,digits=2) => value!==null && value!==undefined && value!=='' && Number.isFinite(Number(value)) ? Number(value).toLocaleString('en-US',{maximumFractionDigits:digits}) : 'Unavailable';
export const percent = value => value!==null && value!==undefined && value!=='' && Number.isFinite(Number(value)) ? `${numeric(Number(value)*100,1)}%` : 'Unavailable';
export function field(path,label,value,options={}) {
 const type=options.type||'number',id='edit-'+path.replaceAll('.','-');
 const attrs=`id="${esc(id)}" data-path="${esc(path)}" data-value-type="${options.valueType||type}"`;
 let control;
 if(options.choices)control=`<select ${attrs}>${options.choices.map(v=>`<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(human(v))}</option>`).join('')}</select>`;
 else if(type==='textarea')control=`<textarea ${attrs} rows="4">${esc(value)}</textarea>`;
 else control=`<input ${attrs} type="${type}" value="${esc(value)}" ${options.min!==undefined?`min="${options.min}"`:''} ${options.max!==undefined?`max="${options.max}"`:''} ${type==='number'?`step="${options.step||'any'}"`:''} ${type==='checkbox'&&value?'checked':''}>`;
 return `<label class="field" for="${esc(id)}"><span>${esc(label)}</span>${control}${options.note?`<small>${esc(options.note)}</small>`:''}</label>`;
}
export const note=(title,text)=>`<aside class="context-note"><strong>${esc(title)}</strong><p>${esc(text)}</p></aside>`;
export function table(title,rows,columns,limit=20){
 if(!Array.isArray(rows)||!rows.length)return `<section class="table-empty"><h3>${esc(title)}</h3><p>No records in this result.</p></section>`;
 return `<div class="table-wrap"><table class="detail-table"><caption>${esc(title)}</caption><thead><tr>${columns.map(c=>`<th scope="col">${esc(c[1])}</th>`).join('')}</tr></thead><tbody>${rows.slice(0,limit).map(r=>`<tr>${columns.map(c=>`<td>${esc(c[2]?c[2](r[c[0]],r):typeof r[c[0]]==='object'?JSON.stringify(r[c[0]]):r[c[0]])}</td>`).join('')}</tr>`).join('')}</tbody></table>${rows.length>limit?`<p class="fine">${limit} of ${rows.length} rows shown. The download includes every row.</p>`:''}</div>`;
}
export function bars(title,rows,label,key,unit=''){
 const max=Math.max(1,...rows.map(r=>Math.abs(Number(r[key])||0)));
 return `<figure class="bar-chart"><figcaption>${esc(title)}</figcaption>${rows.map(r=>`<div class="bar-row"><span>${esc(r[label])}</span><div class="bar-track"><i class="${Number(r[key])<0?'negative':''}" style="width:${Math.abs(Number(r[key])||0)/max*100}%"></i></div><b>${esc(numeric(r[key]))} ${esc(unit)}</b></div>`).join('')}</figure>`;
}
export const status=(text,good)=>`<span class="status-tag ${good?'good':'attention'}">${esc(human(text))}</span>`;
export const facts=(rows)=>`<dl class="fact-list">${rows.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>`;
export const block=(title,body)=>`<section class="work-block"><h3>${esc(title)}</h3>${body}</section>`;
export function applyField(payload,path,value,type){
 const keys=path.split('.');if(keys.some(k=>['__proto__','prototype','constructor'].includes(k)))throw new Error('Invalid input field');
 let node=payload;for(const key of keys.slice(0,-1)){if(!node[key]||typeof node[key]!=='object')throw new Error('This field is missing from the input. Restore a sample.');node=node[key];}
 if(type==='number'){if(value===''||!Number.isFinite(Number(value)))throw new Error('Enter a finite number.');value=Number(value);}
 if(type==='boolean'||type==='checkbox')value=value===true||value==='true';
 if(type==='list')value=String(value).split(',').map(s=>s.trim()).filter(Boolean);
 node[keys.at(-1)]=value;return payload;
}
