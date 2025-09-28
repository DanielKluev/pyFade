"""
Middle layer to control export operation.
Handles the logic of exporting data from pyFADE to various formats.
"""

from py_fade.app import PyFadeApp
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.export_template import ExportTemplate


class ExportController:
    """
    ExportController manages the export of data from pyFADE into datasets of various formats.

    Export is done via templates, which define what samples and completions to include,
    and how to structure the output data.
    """
    def __init__(self, app: "PyFadeApp", dataset: "DatasetDatabase", export_template: "ExportTemplate") -> None:
        """
        Initialize the controller, binding to the app, dataset, and export template.
        """
        self.app = app
        self.dataset = dataset
        self.export_template = export_template