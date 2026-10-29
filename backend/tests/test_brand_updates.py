from app.models import BrandKit, User
from app.schemas import ProjectConfig
from sqlalchemy import select


def test_brand_update_preserves_identity_and_validates_owner(signed,db):
    created=signed.post('/api/brands',json={'name':'Signature'}).json()
    response=signed.put('/api/brands/'+created['id'],json={'name':'New look','captions':{'font':'Poppins','color':'#FF0000','background':True},'resolution':720})
    assert response.status_code==200,response.text
    assert response.json()['id']==created['id']
    assert response.json()['config']['captions']['font']=='Poppins'
    assert response.json()['config']['resolution']==720
    other=User(email='other-brand@example.test',name='Other',password_hash='unused');db.add(other);db.flush()
    foreign=BrandKit(user_id=other.id,name='Private',config={});db.add(foreign);db.commit()
    assert signed.put('/api/brands/'+foreign.id,json={'name':'Changed'}).status_code==404
    assert db.get(BrandKit,foreign.id).name=='Private'
    assert signed.put('/api/brands/'+created['id'],json={'name':'Invalid','captions':{'color':'bad'}}).status_code==422


def test_project_quality_default_validation():
    import pytest
    from pydantic import ValidationError
    assert ProjectConfig().resolution==1080
    assert ProjectConfig(resolution=720).resolution==720
    with pytest.raises(ValidationError):ProjectConfig(resolution=4000)
