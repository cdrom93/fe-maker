import pytest
from fastapi import HTTPException

from fe_maker import api
from fe_maker.folderpick import PickerUnavailable


def test_the_picked_folder_or_none_comes_back(monkeypatch):
    monkeypatch.setattr(api, "pick_folder", lambda title, initial=None: "C:\\Projets\\mon-jeu")
    assert api.pick_folder_endpoint(api.PickFolderIn(title="t")) == {"path": "C:\\Projets\\mon-jeu"}
    monkeypatch.setattr(api, "pick_folder", lambda title, initial=None: None)
    assert api.pick_folder_endpoint(api.PickFolderIn()) == {"path": None}


def test_a_python_without_tk_says_so(monkeypatch):
    def missing(title, initial=None):
        raise PickerUnavailable()

    monkeypatch.setattr(api, "pick_folder", missing)
    with pytest.raises(HTTPException) as e:
        api.pick_folder_endpoint(api.PickFolderIn())
    assert e.value.status_code == 501 and e.value.detail == "pickerUnavailable"
