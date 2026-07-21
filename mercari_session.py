import uuid
import hashlib


class MercariSession:
    """
    Generates Mercari search session id.
    """

    def __init__(self):
        self.session_id = self._generate()


    def _generate(self):
        raw = str(uuid.uuid4())

        return hashlib.md5(
            raw.encode()
        ).hexdigest()


    def get_session_id(self):
        return self.session_id