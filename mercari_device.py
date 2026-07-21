import uuid
from pathlib import Path


class MercariDevice:
    """
    Keeps persistent Mercari device identity.
    """

    def __init__(self, file_path="mercari_device_id.txt"):

        self.file_path = Path(file_path)

        if self.file_path.exists():
            self.device_id = self.file_path.read_text().strip()

        else:
            self.device_id = str(uuid.uuid4())
            self.file_path.write_text(self.device_id)


    def get_device_id(self):
        return self.device_id