from app.recorder.models import SemanticAction
from app.ir.builder import build_ir
from app.ir.validator import validate_ir

def test_ir_build_and_validate():
    actions=[SemanticAction(action='navigate',pageId='page-1',value='http://example.test'), SemanticAction(action='click',pageId='page-1',target={'testId':'go','tag':'button','accessibleName':'Go'},sourceEvents=[2])]
    ir=build_ir(actions,'TC-X','Example')
    assert validate_ir(ir)==[]
    assert ir['steps'][1]['element']=='go'
