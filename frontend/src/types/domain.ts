export type User={id:number;email:string;name:string;role:string};
export type Study={id:number;name:string;filename:string;description:string;categories:string[];raters:string[]};
export type Specimen={id:number;study_id:number;reference:string;description:string};
export type Vote={id:number;specimen_id:number;rater:string;category:string;alternatives:string[]|null};
export type Run={id:number;study_id:number;name:string;status:string;config:any;result:any;kappa:number|null;pbar:number|null;pe:number|null;error?:string};
export type AlternativesRun={id:number;study_id:number;name:string;status:string;config:any;result:any;kappa_min:number|null;kappa_max:number|null;error?:string;created_at?:string};
export type EndpointPlan={vote_id:number;category:string};
export type Memo={id:number;run_id:number|null;alternatives_run_id:number|null;name:string;interpretation:string;next_step:string;result_snapshot:any;status:string;review_note:string};
