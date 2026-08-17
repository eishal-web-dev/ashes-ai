import htmlScan from './scan-html.js';
import spaScan from './scan-spa-flex.js';

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

export default async function handler(request,response){
  const captured=captureResponse();
  await htmlScan(request,captured.response);
  const first=captured.result();

  if(first.statusCode===422&&first.body?.code==='CATALOG_UNREADABLE'){
    return spaScan(request,response);
  }

  for(const [name,value] of first.headers)response.setHeader(name,value);
  if(first.body!==null&&typeof first.body==='object')return response.status(first.statusCode).json(first.body);
  if(first.body!==null)return response.status(first.statusCode).send(first.body);
  return response.status(first.statusCode).end();
}
