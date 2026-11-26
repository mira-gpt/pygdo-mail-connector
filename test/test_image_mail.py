import base64
import unittest
from unittest.mock import MagicMock, patch

from gdo.ui.GDT_Image import GDT_Image


class ImageMailTest(unittest.TestCase):
    def test_file_is_rendered_as_base64_data_url(self):
        image = GDT_Image.__new__(GDT_Image)
        image._width, image._height = '100%', 'auto'
        file = MagicMock()
        file.is_image.return_value = True
        file.get_mime.return_value = 'image/png'
        file._file_data = b'example image bytes'
        with patch.object(image, 'get_file', return_value=[file]), \
             patch.object(image, 'html_attrs', return_value=''), \
             patch.object(image, 'html_alternate', return_value=' alt="example"'):
            result = image.render_mail()
        self.assertIn('data:image/png;base64,' + base64.b64encode(file._file_data).decode(), result)
        self.assertIn('alt="example"', result)

    def test_missing_file_keeps_existing_html_renderer(self):
        image = GDT_Image.__new__(GDT_Image)
        with patch.object(image, 'get_file', return_value=[]), \
             patch.object(image, 'render_html', return_value='<img src="https://example.test/image.png">'):
            self.assertEqual(image.render_html(), image.render_mail())
