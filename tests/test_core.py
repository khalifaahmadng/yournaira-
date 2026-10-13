import os,tempfile
from app.core import detect,handle

def test_parser():
    assert detect("I spent ₦1500 on food")==("expense",150000,"food")
    assert detect("I received ₦5000 salary")==("income",500000,"income")
    assert detect("summary")[0]=="summary"

def test_ledger():
    with tempfile.TemporaryDirectory() as folder:
        os.environ["DATABASE_PATH"]=folder+"/test.db"
        assert "Recorded" in handle("test_session","I spent ₦1500 on food")[1]
        assert "1,500.00" in handle("test_session","summary")[1]
