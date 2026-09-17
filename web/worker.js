/* Run reviewed Python source in an isolated worker; never evaluate user-provided code. */
import { loadPyodide } from './vendor/pyodide/pyodide.mjs';
let ready;
async function initialize(){
  postMessage({type:'progress',message:'Loading Python for the first run. Your scenario data stays in this browser.'});
  const python=await loadPyodide({indexURL:new URL('vendor/pyodide/',self.location.href).href});
  const response=await fetch('application.zip');
  if(!response.ok)throw new Error('Could not load application source.');
  python.unpackArchive(await response.arrayBuffer(),'zip');
  await python.runPythonAsync('import sys\nsys.path.insert(0, ".")\nimport json\nfrom portfolio.registry import execute');
  return python;
}
onmessage=async event=>{
  try{
    ready=ready||initialize();const python=await ready;
    postMessage({type:'progress',message:'Running the same Python code published in the repository…'});
    python.globals.set('request_json',JSON.stringify(event.data));
    const raw=await python.runPythonAsync('request = json.loads(request_json)\njson.dumps(execute(request["project_id"], request["payload"]), allow_nan=False)');
    postMessage({type:'result',report:JSON.parse(raw)});
  }catch(error){ready=null;postMessage({type:'result',error:String(error.message||error).slice(-1200)});}
};
