# coding: utf-8

from google.cloud import secretmanager

class Singleton(type):
    """
    The Singleton class can be implemented in different ways in Python. Some
    possible methods include: base class, decorator, metaclass. We will use the
    metaclass because it is best suited for this purpose.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class SecretManager(metaclass=Singleton):
    """SecretManager is a singleton class to manage secrets from GCP Secret Manager.

    The first time you use this class, you need to call the `initialize` method.
    Thus, you can use the `get_secret` method to retrieve the secret you want.
    
    Usage:
        First use:
        .. code-block:: python
            secret_manager = SecretManager()
            secret_manager.intialize(project_id="<project_id>")
            secret_manager.get_secret(secret_id="<any_secret_id>")

        further uses:
        .. code-block:: python
            secret_manager = SecretManager().get_secret(secret_id="<any_secret_id>")
    """
    def intialize(self, project_id: str):
        """Permits to init the SecretManager client.

        Args:
            project_id (str): project id of the GCP project.
        """
        self._client = secretmanager.SecretManagerServiceClient()
        self._project = project_id

    def _get_secret_path(self, secret_id: str, version: str) -> str:
        """Get the secret path.

        Args:
            secret_id (str): secret id to retrieve
            version (str): version of the secret to retrieve

        Returns:
            str: name of the secret path that is required to retrieve the secret.
        """
        return self._client.secret_version_path(
            project=self._project, secret=secret_id, secret_version=version
        )
    
    def _get_secret_payload(self, name: str) -> str:
        """Performs the request to retrieve the secret payload from the secret
        path given in parameter.

        Args:
            name (str): the secret path

        Returns:
            str: decoded secret payload ready to use.

        Raises:
            google.api_core.exceptions.NotFound: if the secret is not found.
        """
        # TODO: "Add labels to the request"
        request = secretmanager.AccessSecretVersionRequest(name=name)#, labels={"env": "prod"})
        response = self._client.access_secret_version(request=request)
        
        # Return the secret payload
        payload = response.payload.data.decode('UTF-8')

        return payload
    
    def _check_initialized(self):
        """Ensure that the SecretManager is initialized.
        This means that the `_client` attribute is set.

        Raises:
            RuntimeError: the SecretManager is not initialized yet.
        """
        if not hasattr(self, "_client"):
            raise RuntimeError(
                "SecretManager not initialized. "
                "Ensure to call `initialize` method first."
            )
    
    def get_secret(self, secret_id: str, version: str = "latest" ) -> str:
        """Returns the secret payload from the secret id and version given in parameter.
        By default, the version is set to "latest".

        Args:
            secret_id (str): secret id to retrieve
            version (str, optional): version of the secret to retrieve . Defaults to "latest".

        Returns:
            str: secret value.

        Raises:
            google.api_core.exceptions.NotFound: if the secret is not found.
        """
        self._check_initialized()
        secret_path = self._get_secret_path(secret_id=secret_id, version=version)
        return self._get_secret_payload(name=secret_path)
