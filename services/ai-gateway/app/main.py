from fastapi import FastAPI
app=FastAPI(title="AI Gateway",version="0.1.0")
@app.get('/health')
def health(): return {'status':'UP','service':'ai-gateway'}
@app.get('/api/v1/ai/capabilities')
def capabilities():
    return {'capabilities':['failure-analysis','test-data-generation','bug-draft','code-explanation']}
