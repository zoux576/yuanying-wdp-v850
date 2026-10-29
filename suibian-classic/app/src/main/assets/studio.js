'use strict';
(function(){
const T={
 appName:'\u7ecf\u5178 AI \u521b\u4f5c',heroKicker:'\u53cc\u6765\u6e90\u30fb\u81ea\u7531\u5207\u6362',heroOne:'\u4fdd\u7559\u719f\u6089\u7684',heroTwo:'\u521b\u4f5c\u65b9\u5f0f',heroSub:'\u4e0d\u66ff\u6362\u5b98\u65b9\u5e94\u7528\uff0c\u4e00\u952e\u5207\u6362\u53cc\u6a21\u5f0f\u3002',chooseSource:'\u9009\u62e9 AI \u6765\u6e90',customMode:'\u81ea\u5b9a\u4e49 API',noSuibianLogin:'\u4e0d\u9700\u968f\u53d8\u767b\u5f55',officialMode:'\u968f\u53d8\u5b98\u65b9 AI',officialAccount:'\u4f9d\u5b98\u65b9\u8d26\u53f7\u4f7f\u7528',createStep:'\u521b\u4f5c',chooseCreation:'\u60f3\u521b\u4f5c\u4ec0\u4e48\uff1f',textToImage:'\u6587\u5b57\u751f\u56fe',imageEdit:'\u53c2\u8003\u6539\u56fe',videoCreate:'\u6587\u5b57\u751f\u89c6\u9891',promptLabel:'\u521b\u610f\u63d0\u793a\u8bcd',promptPlaceholder:'\u63cf\u8ff0\u4eba\u7269\u3001\u573a\u666f\u3001\u5149\u5f71\u548c\u4f60\u671f\u671b\u7684\u753b\u9762\u2026',promptTip:'\u63cf\u8ff0\u4e3b\u4f53\u3001\u73af\u5883\u3001\u5149\u7ebf\u4e0e\u98ce\u683c\uff0c\u6548\u679c\u66f4\u7a33\u5b9a\u3002',clear:'\u6e05\u7a7a',referenceImage:'\u53c2\u8003\u56fe\u7247',selectImage:'\u9009\u62e9\u53c2\u8003\u56fe',imageLimit:'JPG/PNG/WebP\uff0c\u4e0a\u4f20\u524d\u81ea\u52a8\u538b\u7f29',removeImage:'\u79fb\u9664\u56fe\u7247',parametersStep:'\u53c2\u6570',fineTune:'\u81ea\u7531\u8c03\u6574\u751f\u6210\u53c2\u6570',model:'\u6a21\u578b',size:'\u753b\u9762\u5c3a\u5bf8',duration:'\u89c6\u9891\u65f6\u957f\uff08\u79d2\uff09',ratio:'\u89c6\u9891\u6bd4\u4f8b',apiTitle:'AI \u63a5\u53e3\u8bbe\u7f6e',apiSubtitle:'\u81ea\u7531\u914d\u7f6e HTTPS \u5730\u5740\u4e0e\u6a21\u578b',apiUrl:'API \u57fa\u7840\u5730\u5740',apiKey:'API \u5bc6\u94a5',generatePath:'\u751f\u56fe\u8def\u5f84',editPath:'\u6539\u56fe\u8def\u5f84',videoPath:'\u89c6\u9891\u8def\u5f84\uff08\u4f9b\u5e94\u5546\u81ea\u5b9a\u4e49\uff09',saveKeyNote:'\u5728\u672c\u673a\u4fdd\u5b58\u5bc6\u94a5\uff08\u9ed8\u8ba4\u5173\u95ed\uff09',testConnection:'\u6d4b\u8bd5\u8fde\u63a5\uff08\u4e0d\u6263\u751f\u6210\u8d39\uff09',httpsOnly:'\u4ec5\u5141\u8bb8 HTTPS',generate:'\u5f00\u59cb\u751f\u6210',billingNote:'\u751f\u6210\u53ef\u80fd\u6263\u8d39\uff0c\u5931\u8d25\u4e0d\u81ea\u52a8\u91cd\u8bd5\u3002',resultsStep:'\u7ed3\u679c',latestResult:'\u6700\u65b0\u521b\u4f5c\u7ed3\u679c',ready:'\u5c31\u7eea',resultPlaceholder:'\u521b\u4f5c\u6210\u679c\u4f1a\u663e\u793a\u5728\u8fd9\u91cc',resultSub:'\u914d\u7f6e API\uff0c\u5199\u4e0b\u63d0\u793a\u8bcd\uff0c\u5f00\u59cb\u521b\u4f5c\u3002',saveImage:'\u4fdd\u5b58\u5230\u76f8\u518c',originalOfficial:'\u8df3\u8f6c\u539f\u7248',officialHeading:'\u7ee7\u7eed\u4f7f\u7528\u5b98\u65b9\u968f\u53d8',officialDescription:'\u6b64\u6a21\u5f0f\u6253\u5f00\u5df2\u5b89\u88c5\u7684\u672a\u4fee\u6539\u968f\u53d8\u5b98\u65b9\u5e94\u7528\u3002\u5b98\u65b9\u751f\u6210\u529f\u80fd\u4e0e\u767b\u5f55\u72b6\u6001\u4ecd\u7531\u53d1\u884c\u65b9\u63a7\u5236\u3002',keepOfficial:'\u539f\u7248 38.8.1 \u53ca\u8d26\u53f7\u6570\u636e\u4e0d\u53d8',noBypass:'\u4e0d\u66f4\u6539\u5b98\u65b9\u7b7e\u540d\u6216\u7ed5\u8fc7\u767b\u5f55',openOfficial:'\u6253\u5f00\u5b98\u65b9\u968f\u53d8',officialLimit:'\u672a\u83b7\u5f97\u5b98\u65b9\u6e38\u5ba2 API \u6388\u6743\uff0c\u56e0\u6b64\u4e0d\u4f1a\u5728\u8fd9\u91cc\u4f2a\u9020\u514d\u767b\u5f55\u7684\u5b98\u65b9\u751f\u6210\u3002\u6253\u5f00\u539f\u7248\u4e5f\u4e0d\u4fdd\u8bc1\u8fdb\u5165\u65e7\u521b\u4f5c\u9875\u3002',footerFirst:'\u72ec\u7acb\u5de5\u5177 \u00b7 \u4e0d\u6539\u52a8\u5b98\u65b9\u5e94\u7528',show:'\u663e\u793a',hide:'\u9690\u85cf',errUrl:'\u8bf7\u5148\u586b\u5199\u6709\u6548\u7684 HTTPS API \u5730\u5740',errPrompt:'\u8bf7\u5148\u8f93\u5165\u63d0\u793a\u8bcd',errModel:'\u8bf7\u586b\u5199\u6a21\u578b\u540d\u79f0',errReference:'\u8bf7\u5148\u9009\u62e9\u53c2\u8003\u56fe',pending:'\u5904\u7406\u4e2d',success:'\u5df2\u5b8c\u6210',failed:'\u5931\u8d25',connectionSuccess:'API \u8fde\u63a5\u6210\u529f',connectionFailed:'API \u8fde\u63a5\u5931\u8d25',videoPending:'\u5df2\u63d0\u4ea4\u89c6\u9891\u4efb\u52a1\uff0c\u8bf7\u5728\u63d0\u4f9b\u5546\u68c0\u67e5\u72b6\u6001',imageChosen:'\u5df2\u9009\u62e9\u53c2\u8003\u56fe',imageSaved:'\u56fe\u7247\u5df2\u63d0\u4ea4\u4fdd\u5b58',offlineBrowser:'\u6d4f\u89c8\u5668\u4e2d\u9700\u8981 API \u652f\u6301 CORS\uff1b\u5b89\u5353\u5e94\u7528\u4f7f\u7528\u539f\u751f\u7f51\u7edc\u901a\u9053\u3002',taskId:'\u4efb\u52a1\u7f16\u53f7',checkDocs:'\u89c6\u9891\u4efb\u52a1\u56de\u4f20\u56e0\u5546\u6237\u800c\u5f02\uff0c\u9700\u8981\u5bf9\u5e94\u7684\u72b6\u6001\u67e5\u8be2\u63a5\u53e3\u3002',nativeRequired:'\u8bf7\u5728\u5b89\u5353\u5e94\u7528\u4e2d\u6253\u5f00\u5b98\u65b9\u968f\u53d8',readyToDownload:'\u5df2\u83b7\u53d6\u7ed3\u679c\uff0c\u53ef\u4fdd\u5b58',configHelp:'\u8bf7\u5148\u5c55\u5f00 API \u8bbe\u7f6e\u586b\u5199\u5730\u5740\u3002'
};
T.saveKeyNote='在安卓密钥库加密保存 API 密钥（默认关闭）';
const $=id=>document.getElementById(id);
const state={source:'custom',kind:'image',busy:false,inFlight:null,requestCounter:0,referenceData:null,lastImage:null,lastVideo:null,toastTimer:null,modelByKind:{image:'gpt-image-1',edit:'gpt-image-1',video:'video-model'}};
function localize(){document.querySelectorAll('[data-i18n]').forEach(el=>{const txt=T[el.dataset.i18n];if(txt)el.textContent=txt;});document.querySelectorAll('[data-placeholder]').forEach(el=>{el.placeholder=T[el.dataset.placeholder]||el.placeholder;});}
function toast(message,error){const el=$('toast');el.textContent=message;el.classList.toggle('error',!!error);el.classList.add('show');clearTimeout(state.toastTimer);state.toastTimer=setTimeout(()=>el.classList.remove('show'),5000);}
function safeStorageSet(key,val){try{localStorage.setItem(key,JSON.stringify(val));}catch(e){}}
function safeStorageGet(key,fallback){try{const t=localStorage.getItem(key);return t===null?fallback:JSON.parse(t);}catch(e){return fallback;}}
const persisted=['baseUrl','model','size','generatePath','editPath','videoPath','prompt','duration','aspect'];
function saveDraft(){const cfg={};for(const id of persisted)cfg[id]=$(id).value;state.modelByKind[state.kind]=$('model').value;cfg.modelByKind={...state.modelByKind};cfg.rememberKey=$('rememberKey').checked;safeStorageSet('classic_ai_dual_settings_v1',cfg);}
function persistKey(){if(window.Native&&typeof window.Native.persistKey==='function'){if(!window.Native.persistKey($('apiKey').value,$('rememberKey').checked))toast('保存加密密钥失败，请检查本机密钥库',true);}}
function loadDraft(){const cfg=safeStorageGet('classic_ai_dual_settings_v1',{});for(const id of persisted){if(typeof cfg[id]==='string')$(id).value=cfg[id];}if(cfg.modelByKind && typeof cfg.modelByKind==='object')state.modelByKind={...state.modelByKind,...cfg.modelByKind};if(cfg.rememberKey){$('rememberKey').checked=true;if(window.Native&&typeof window.Native.restoreKey==='function'){$('apiKey').value=window.Native.restoreKey()||'';}}setPromptCount();}
function setSource(src){state.source=src;const isCustom=src==='custom';$('customSection').hidden=!isCustom;$('officialSection').hidden=isCustom;document.querySelectorAll('.source-tab').forEach(el=>{const active=el.dataset.source===src;el.classList.toggle('active',active);el.setAttribute('aria-selected',String(active));});}
function setKind(kind){if(kind!==state.kind){state.modelByKind[state.kind]=$('model').value;state.kind=kind;$('model').value=state.modelByKind[kind]||'gpt-image-1';}document.querySelectorAll('.task').forEach(el=>{const active=el.dataset.kind===kind;el.classList.toggle('active',active);el.setAttribute('aria-selected',String(active));});$('referenceWrap').hidden=kind!=='edit';$('videoOptions').hidden=kind!=='video';$('size').closest('.field').hidden=kind==='video';$('videoPath').closest('.field').hidden=false;saveDraft();}
function setPromptCount(){$('promptCount').textContent=$('prompt').value.length+' / 3000';}
function expandSettings(expand){$('apiContent').hidden=!expand;$('apiToggle').setAttribute('aria-expanded',String(expand));$('apiChevron').classList.toggle('rotated',expand);}
function normalizeBaseUrl(value){const raw=(value||'').trim();if(!raw)throw Error(T.errUrl);let u;try{u=new URL(raw);}catch(e){throw Error(T.errUrl);}if(u.protocol!=='https:'||!u.hostname||u.username||u.password||u.hash)throw Error(T.errUrl);if(u.search)throw Error(T.errUrl);return u.href.replace(/\/$/,'');}
function resolveEndpoint(base,path){const url=normalizeBaseUrl(base);let suffix=(path||'').trim();if(!suffix.startsWith('/')||suffix.startsWith('//')||suffix.includes('?')||suffix.includes('#')||suffix.includes('..'))throw Error('Invalid endpoint path');suffix=suffix.replace(/\/+/g,'/');if(url.endsWith('/v1')&&suffix.startsWith('/v1/'))suffix=suffix.slice(3);return url+suffix;}
function inputPayload(type){const baseUrl=normalizeBaseUrl($('baseUrl').value);let path=type==='test'?'/models':state.kind==='edit'?$('editPath').value:state.kind==='video'?$('videoPath').value:$('generatePath').value;const url=resolveEndpoint(baseUrl,path);const model=$('model').value.trim();const prompt=$('prompt').value.trim();if(type!=='test'&&!prompt)throw Error(T.errPrompt);if(type!=='test'&&!model)throw Error(T.errModel);if(type!=='test'&&state.kind==='edit'&&!state.referenceData)throw Error(T.errReference);return {type,url,apiKey:$('apiKey').value.trim(),kind:state.kind,model,prompt,size:$('size').value,duration:Number($('duration').value),aspect_ratio:$('aspect').value,imageData:state.kind==='edit'?state.referenceData:null};}
function busy(flag){state.busy=!!flag;$('generateButton').disabled=!!flag;$('testConnection').disabled=!!flag;$('resultTag').textContent=flag?T.pending:T.ready;$('generateButton').querySelector('[data-i18n="generate"]').textContent=flag?T.pending:T.generate;}
function showResult(data,resultKind){const content=$('resultContent');const img=$('resultImage');const vid=$('resultVideo');const raw=$('resultRaw');const task=$('taskId');$('emptyResult').hidden=true;content.hidden=false;img.hidden=true;vid.hidden=true;raw.hidden=true;task.hidden=true;$('saveResult').hidden=true;state.lastImage=null;state.lastVideo=null;
 const list=Array.isArray(data.data)?data.data:[];const first=list[0]||{};const result=data.output||data.result||{};const image=data.dataUrl||data.image_url||data.imageUrl||first.url||first.b64_json&&('data:image/png;base64,'+first.b64_json)||(Array.isArray(data.images)&&data.images[0]&&(data.images[0].url||data.images[0].b64_json&&('data:image/png;base64,'+data.images[0].b64_json)))||result.image_url||'';
 const video=data.video_url||data.videoUrl||data.video&&data.video.url||result.video_url||result.url||(resultKind==='video'&&(data.url||first.url))||'';
 if(resultKind==='video'&&video){vid.src=video;vid.hidden=false;state.lastVideo=video;$('resultTag').textContent=T.success;return;}
 if(image){img.src=image;img.hidden=false;state.lastImage=image;$('saveResult').hidden=false;$('resultTag').textContent=T.success;return;}
 if(video){vid.src=video;vid.hidden=false;state.lastVideo=video;$('resultTag').textContent=T.success;return;}
 if(data.task_id||data.id||data.status==='queued'||data.status==='processing'){$('resultTag').textContent=T.pending;task.textContent=T.videoPending+'\n'+T.taskId+': '+(data.task_id||data.id||'--')+'\n'+T.checkDocs;task.hidden=false;return;}
 raw.textContent=JSON.stringify(data,null,2).slice(0,5000);raw.hidden=false;$('resultTag').textContent=T.success;
}
function showFailure(message){
 const content=$('resultContent');const raw=$('resultRaw');
 $('emptyResult').hidden=true;content.hidden=false;
 $('resultImage').hidden=true;$('resultVideo').hidden=true;$('taskId').hidden=true;$('saveResult').hidden=true;
 state.lastImage=null;state.lastVideo=null;
 raw.hidden=false;raw.textContent='请求失败：'+String(message||'未知错误')+'\n生成请求不会自动重试。若已经扣费，请先在服务商检查任务记录，避免重复付费。';
 $('resultTag').textContent=T.failed;
}
function showModels(result){
 const items=Array.isArray(result&&result.data)?result.data:[];
 const ids=items.map(x=>x&&x.id).filter(x=>typeof x==='string'&&x.length<128).slice(0,80);
 const list=$('modelsList');list.textContent='';
 for(const id of ids){const option=document.createElement('option');option.value=id;list.appendChild(option);}
 $('connectionStatus').textContent=ids.length?'已连接；检测到 '+ids.length+' 个模型，可在模型输入框选择':'连接成功，但未返回标准模型列表；可手动填写模型';
}
window.classicReceive=function(response){
 let data=response;try{if(typeof data==='string')data=JSON.parse(data);}catch(e){data={ok:false,error:'Invalid native response'};}
 if(!data||typeof data!=='object')data={ok:false,error:'Invalid response'};
 if(state.inFlight && data.requestId && data.requestId!==state.inFlight.requestId)return;
 const context=state.inFlight;
 const kind=data.kind||(context&&context.kind)||state.kind;
 state.inFlight=null;busy(false);
 if(data.type==='test'){
   if(data.ok)showModels(data.result||{});
   else $('connectionStatus').textContent='连接失败：'+String(data.error||'未知错误').slice(0,350);
   toast(data.ok?T.connectionSuccess:T.connectionFailed+': '+(data.error||''),!data.ok);return;
 }
 if(!data.ok){showFailure(data.error);toast(String(data.error||T.failed),true);return;}
 showResult(data.result||data,kind);
 toast(data.result&&(data.result.task_id||data.result.status==='queued')?T.videoPending:T.readyToDownload,false);
};
async function browserRequest(req){
 try{
 const headers={'Accept':'application/json'};
 if(req.apiKey)headers.Authorization='Bearer '+req.apiKey;
 const opts={method:req.type==='test'?'GET':'POST',headers};
 if(req.type!=='test'){
   if(req.kind==='edit'){
     const form=new FormData();form.append('model',req.model);form.append('prompt',req.prompt);form.append('size',req.size);
     const res=await fetch(req.imageData);const blob=await res.blob();form.append('image',blob,'reference.jpg');opts.body=form;
   }else{
     headers['Content-Type']='application/json';
     opts.body=JSON.stringify(req.kind==='video'?{model:req.model,prompt:req.prompt,duration:req.duration,aspect_ratio:req.aspect_ratio}:{model:req.model,prompt:req.prompt,size:req.size});
   }
 }
 const res=await fetch(req.url,opts);const text=await res.text();let data;
 try{data=JSON.parse(text);}catch(e){throw Error('HTTP '+res.status+' 返回了非 JSON 内容');}
 if(!res.ok)throw Error('HTTP '+res.status+' '+String(data.error&&data.error.message||JSON.stringify(data)).slice(0,500));
 window.classicReceive({ok:true,type:req.type,kind:req.kind,requestId:req.requestId,result:data});
 }catch(e){window.classicReceive({ok:false,type:req.type,kind:req.kind,requestId:req.requestId,error:String(e.message||e)+'; '+T.offlineBrowser});}
}
function dispatch(type){
 if(state.busy)return;
 let req;try{req=inputPayload(type);}catch(e){if(!$('baseUrl').value.trim())expandSettings(true);toast(e.message,true);return;}
 req.requestId=String(Date.now())+'-'+String(++state.requestCounter);
 state.inFlight={requestId:req.requestId,kind:req.kind,type};
 if(type==='generate'&&state.kind==='video')toast(T.checkDocs,false);
 busy(true);
 try{if(window.Native&&typeof window.Native.perform==='function')window.Native.perform(JSON.stringify(req));else browserRequest(req);}
 catch(e){state.inFlight=null;busy(false);showFailure(e.message);toast(e.message,true);}
}
function saveImage(){const image=state.lastImage;if(!image)return;if(window.Native&&typeof window.Native.saveImage==='function'){try{window.Native.saveImage(image,'classic-ai-'+Date.now()+'.png');toast(T.imageSaved);return;}catch(e){toast(String(e),true);return;}}
 try{const a=document.createElement('a');a.href=image;a.download='classic-ai-'+Date.now()+'.png';document.body.appendChild(a);a.click();a.remove();}catch(e){toast(String(e),true);}}
function openOfficial(){if(window.Native&&typeof window.Native.openOfficial==='function'){window.Native.openOfficial();return;}toast(T.nativeRequired,true);}
async function compressImage(file){if(file.size>24*1024*1024)throw Error('Input image exceeds 24MB');const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('Unable to read image'));reader.readAsDataURL(file);});const img=await new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=()=>reject(Error('Invalid image'));i.src=dataUrl;});const ratio=Math.min(1,1800/Math.max(img.width,img.height));const cv=document.createElement('canvas');cv.width=Math.max(1,Math.round(img.width*ratio));cv.height=Math.max(1,Math.round(img.height*ratio));const cx=cv.getContext('2d');cx.drawImage(img,0,0,cv.width,cv.height);let quality=.85;let out=cv.toDataURL('image/jpeg',quality);while(out.length>4.6e6&&quality>.3){quality-=.1;out=cv.toDataURL('image/jpeg',quality);}if(out.length>7e6)throw Error('Compressed reference is too large');return out;}
function init(){localize();loadDraft();setSource('custom');setKind('image');document.querySelectorAll('.source-tab').forEach(x=>x.addEventListener('click',()=>setSource(x.dataset.source)));document.querySelectorAll('.task').forEach(x=>x.addEventListener('click',()=>setKind(x.dataset.kind)));$('apiToggle').addEventListener('click',()=>expandSettings($('apiContent').hidden));$('clearPrompt').addEventListener('click',()=>{$('prompt').value='';setPromptCount();saveDraft();});$('prompt').addEventListener('input',()=>{setPromptCount();saveDraft();});for(const id of persisted.filter(x=>x!=='prompt'))$(id).addEventListener('change',saveDraft);$('rememberKey').addEventListener('change',()=>{saveDraft();persistKey();});$('apiKey').addEventListener('input',()=>{if($('rememberKey').checked)persistKey();});$('showKey').addEventListener('click',()=>{const el=$('apiKey');const reveal=el.type==='password';el.type=reveal?'text':'password';$('showKey').textContent=reveal?T.hide:T.show;});$('generateButton').addEventListener('click',()=>dispatch('generate'));$('testConnection').addEventListener('click',()=>dispatch('test'));$('saveResult').addEventListener('click',saveImage);$('openOfficial').addEventListener('click',openOfficial);$('removeReference').addEventListener('click',()=>{state.referenceData=null;$('referenceInput').value='';$('referencePreview').src='';$('referencePreview').hidden=true;$('removeReference').hidden=true;});$('referenceInput').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{const dat=await compressImage(file);state.referenceData=dat;$('referencePreview').src=dat;$('referencePreview').hidden=false;$('removeReference').hidden=false;toast(T.imageChosen);}catch(err){toast(err.message,true);}});}
window.classicNativeToast=(message,isError)=>toast(String(message),!!isError);
window.classicTest={normalizeBaseUrl,resolveEndpoint,inputPayload,showResult,setSource,setKind,dispatch,saveDraft};
init();
})();
