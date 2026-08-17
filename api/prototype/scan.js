import htmlScan from './scan-html.js';
import spaScan from './scan-spa-flex.js';
import genericScan from './scan-generic.js';

export const config={maxDuration:60};

function captureResponse(){
  let statusCode=200;
  let body=null;
  const headers=new Map();
  const response={
    setHeader(name,value){headers.set(String(name),value);return response;},
    status(code){statusCode=Number(code)||500;return response;},
    json(value){body=value;return response;},
    send(value){body=value;return response;},
    end(value){if(value!==undefined)body=value;return response;},
  };
  return {response,result:()=>({statusCode,body,headers})};
}

function forward(result,response){
  for(const [name,value] of result.headers)response.setHeader(name,value);
  if(result.body!==null&&typeof result.body==='object')return response.status(result.statusCode).json(result.body);
  if(result.body!==null)return response.status(result.statusCode).send(result.body);
  return response.status(result.statusCode).end();
}

export default async function handler(request,response){
  const structured=captureResponse();
  await htmlScan(request,structured.response);
  const first=structured.result();
  if(first.statusCode>=200&&first.statusCode<300)return forward(first,response);

  if(first.statusCode===422&&first.body?.code==='CATALOG_UNREADABLE'){
    const spa=captureResponse();
    await spaScan(request,spa.response);
    const second=spa.result();
    if(second.statusCode>=200&&second.statusCode<300)return forward(second,response);
    if(second.statusCode===422&&['SPA_CATALOG_UNREADABLE','CATALOG_UNREADABLE'].includes(second.body?.code)){
      return genericScan(request,response);
    }
    return forward(second,response);
  }

  return forward(first,response);
}
