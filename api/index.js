'use strict';
const {app}=require('@azure/functions');
const {review}=require('./review.cjs');
app.http('practice-review',{methods:['POST'],authLevel:'anonymous',route:'practice-review',handler:review});
