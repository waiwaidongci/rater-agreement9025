import {request,post,patch} from './client';
export const researchApi={
 runs:()=>request('/runs'),
 memos:()=>request('/memos'),
 createRun:(data:any)=>post('/runs',data),
 createMemo:(data:any)=>post('/memos',data),
 approve:(id:number,data:any)=>patch('/memos/'+id+'/approval',data),
 alternativesRuns:()=>request('/alternatives-runs'),
 alternativesRun:(id:number)=>request('/alternatives-runs/'+id),
 preflight:(data:{study_id:number})=>post('/alternatives-runs/preflight',data),
 createAlternativesRun:(data:any)=>post('/alternatives-runs',data),
 verifyPlan:(id:number,data:any)=>post('/alternatives-runs/'+id+'/verify',data)
};
