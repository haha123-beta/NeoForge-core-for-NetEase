"""Scalar invocation-conversion identities; no class-name heuristics."""
BOXES={p:'java.lang.'+b for p,b in [('boolean','Boolean'),('byte','Byte'),
    ('short','Short'),('char','Character'),('int','Integer'),('long','Long'),
    ('float','Float'),('double','Double')]}
UNBOXES={b:p for p,b in BOXES.items()}
WIDENS={'byte':('short','int','long','float','double'),
        'short':('int','long','float','double'),'char':('int','long','float','double'),
        'int':('long','float','double'),'long':('float','double'),
        'float':('double',),'double':(),'boolean':()}

def widens(actual,target):
    return actual==target or target in WIDENS.get(actual,())
