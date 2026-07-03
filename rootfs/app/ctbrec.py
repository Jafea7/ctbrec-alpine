""" Simple Python client for programmatic interaction with the CTBRec server

###################################################################################
WARNING - Make a backup of your server.json file before using the CtbRec class !!!!
###################################################################################

CTBRec server functionality that is exposed includes:
* querying server state and status
* updating server settings (including raw config access)
* getting/adding/modifying/deleting models
* getting/adding/modifying/deleting model-groups
* getting/deleting/post-processing recordings
* model notes management
* debug information access

Tested with ctbrec-server version 5.3.2, and Python version 3.9+
"""

import json
from datetime import datetime
from enum import Enum
from typing import Union, Mapping, Optional, List, Dict, Any
import uuid
import re
import hmac
import hashlib
import warnings
from urllib.parse import quote

from urllib3.exceptions import InsecureRequestWarning
import requests


class CtbRecRequestFailed(Exception):
    """ Exception to be raised if ctbrec server returns status=='fail' """
    pass


class CtbRecInvalidModelDefinition(Exception):
    """ Exception to be raised model definition doesn't conform to recognised pattern """
    pass


class CtbRecNotFound(Exception):
    """ Exception to be raised if an attempt to match a model or group on the server fails """
    pass


class CtbRecAlreadyExists(Exception):
    """ Exception to be raised if an attempt is made to create a model-group that already exists"""
    pass


class CtbRec:
    """
    Simple Python interface to the awesome ctbrec-server.
    
    This client provides programmatic access to manage recordings, models, 
    model groups, and server settings.
    
    Example:
        >>> ctb = CtbRec('https://localhost:8443', 'username', 'password')
        >>> models = ctb.get_models()
        >>> print(ctb.get_summary())
    """

    # basic regular expressions for model strings/urls
    regex = {
        'url': re.compile('https?://'),
        'site_name': re.compile(r'[A-Z]\w+:[\w-]+'),
        'domain_name': re.compile(r'https?://([\w-]+\.)*([\w-]+\.[\w-]+)/([\w-]+/)*(.*)/??$'),
        'model_type': re.compile(r'ctbrec\.sites\.[\w]+\.(\w+)Model')
    }

    class ModelType(Enum):
        """ Used for identifying model input type """
        url = 1
        site_name = 2
        model_dict = 3

    def __init__(self, server_url: str, username: str = None, password: str = None, verify: Union[bool, str] = False):
        """
        Initialise server connection.

        Args:
            server_url: URL of the ctbrec server, e.g. https://localhost:8443
            username: Optional ctbrec server username. Default is None.
            password: Optional ctbrec server password. Default is None.
            verify: Passed through to requests.Session for server SSL certificate handling. 
                    Can be True, False, or path to CA bundle. Default is False.
        """
        # ignore insecure request warnings when tls is being used
        warnings.simplefilter(action='ignore', category=InsecureRequestWarning)
        # initialise connection parameters
        self.server_url = server_url.strip("/")
        self.session = requests.Session()
        if username is not None or password is not None:
            self.session.auth = (username, password)
        self.session.verify = verify
        self.session.headers.update({'X-Requested-With': 'XMLHttpRequest'})
        # get hmac key
        hmac_req = self.session.get(self.server_url + '/secured/hmac')
        if hmac_req.status_code == 200 and len(hmac_req.text) > 0:
            self.hmac_key = json.loads(hmac_req.text)['hmac'].encode('utf-8')
        else:
            self.hmac_key = b''
        # keep copy of initial server config
        self.initial_config = self.get_settings()
        self.initial_models = self.get_models()
        self.initial_model_groups = self.get_model_groups()

    # ----------------------------------------- model methods ---------------------------------------------------------
    def get_models(self, online: bool = False) -> Mapping[str, dict]:
        """
        Get a list of all models on the server.

        Args:
            online: If True then only retrieve online models, else return all models. Default is False.
            
        Returns:
            Dict of models where key is Site:ModelName.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        ml = self.send_request(url='/rec', data={'action': 'listOnline' if online else 'list'})['models']
        return {self.model_id(m): m for m in ml}

    def get_currently_recording(self) -> Mapping[str, dict]:
        """
        Get a list of models currently being recorded.

        Returns:
            Dict of models where key is Site:ModelName.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        ml = self.send_request(url='/rec', data={'action': 'listCurrentlyRecording'})['models']
        return {self.model_id(m): m for m in ml}

    def get_model_status(self) -> Mapping[str, str]:
        """
        Get status code for all models.

        Returns:
            Dict with status for each Site:Model. Status can be one of:
            ["recording", "online", "offline", "paused", "later", "downtime"]
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        m = self.get_models()
        o = self.get_models(online=True)
        r = self.get_recordings()
        result = dict.fromkeys(m.keys(), 'offline')
        result.update(dict.fromkeys(o.keys(), 'online'))
        result.update(dict.fromkeys({self.model_id(i['model']) for i in r if i['status'] == 'RECORDING'}, 'recording'))
        result.update(dict.fromkeys({k for k, v in m.items() if v.get('bookmarked', v.get('markedForLater', False))}, 'later'))
        result.update(dict.fromkeys({k for k, v in m.items() if v['suspended']}, 'paused'))
        # Check for downtime
        for k, v in m.items():
            if self._is_in_downtime(v):
                result[k] = 'downtime'
        return result

    def _is_in_downtime(self, model: dict) -> bool:
        """Check if a model is currently in its downtime period."""
        start = model.get('downtimeStart', '00:00')
        end = model.get('downtimeEnd', '00:00')
        if start == end or (start == '00:00' and end == '00:00'):
            return False
        try:
            from datetime import datetime
            now = datetime.now().time()
            start_time = datetime.strptime(start, '%H:%M').time()
            end_time = datetime.strptime(end, '%H:%M').time()
            if start_time <= end_time:
                return start_time <= now <= end_time
            else:  # spans midnight
                return now >= start_time or now <= end_time
        except (ValueError, TypeError):
            return False

    def add_model(self, model: Union[str, dict], props: dict = None) -> dict:
        """
        Add a model to the server.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            props: Optional dict of one or more model definition items to update. These can include:
                   'priority' (int), 'suspended' (bool), 'bookmarked' (bool),
                   'recordUntil' (int|datetime), 'recordUntilSubsequentAction' (str),
                   'preferredResolution' (int), 'preferHigherBitrate' (bool),
                   'downtimeStart' (str HH:MM), 'downtimeEnd' (str HH:MM).
                   
        Returns:
            The model dict if successfully added.
            
        Raises:
            CtbRecInvalidModelDefinition: If model format is not recognized.
            CtbRecNotFound: If model could not be found after adding.
            CtbRecRequestFailed: If the server request fails.
        """
        if props:
            props = self.parse_model_props(props)

        # determine model specification type
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            model = self.parse_model_props(model)
            if props:
                model.update(props)
            data = {'action': 'start', 'model': model}
        elif mt == self.ModelType.site_name:
            data = {'action': 'startByName', 'model': {"type": None, "name": "", "url": model}}
        elif mt == self.ModelType.url:
            data = {'action': 'startByUrl', 'model': {"type": None, "name": "", "url": model}}
        else:
            data = {}  # should never reach here because parse_model_type will raise an exception
        # query the server
        self.send_request("/rec", data=data)
        # retrieve model back from server
        m = self.find_model(model)
        # update model dict with optional additional properties
        if props and mt != self.ModelType.model_dict:
            m = self.update_model(m, props)
        return m

    def add_models(self, models: List[Union[str, dict]], props: dict = None) -> list:
        """
        Add a list of models to the server, catching any exceptions.

        Args:
            models: A list of model definitions - one of [url[str], Site:Name[str], ModelDict[dict]]
            props: Optional dict of one or more model definition items that will be applied to all models.
                   
        Returns:
            A list of any models successfully added.
        """
        models_added = []
        for m in models:
            try:
                models_added.append(self.add_model(m, props))
            except (CtbRecRequestFailed, CtbRecInvalidModelDefinition) as error:
                warnings.warn(f'Unable to add {m} to server: {error}')
            except CtbRecNotFound:
                warnings.warn(f'{m} added but could not be matched on server')
        return models_added

    def bulk_add_models(self, models: List[Union[str, dict]], props: dict = None) -> dict:
        """
        Add a list of models to the server in a single bulk request.

        Args:
            models: A list of model definitions - one of [url[str], Site:Name[str], ModelDict[dict]]
            props: Optional dict of one or more model definition items to apply to all added models.
                   
        Returns:
            Success message dict.
            
        Raises:
            CtbRecInvalidModelDefinition: If model format is not recognized.
            CtbRecRequestFailed: If the server request fails.
        """
        payload_models = []
        for m in models:
            mt = self.parse_model_type(m)
            if mt == self.ModelType.model_dict:
                model_dict = self.parse_model_props(m)
                if props:
                    model_dict.update(props)
            elif mt == self.ModelType.site_name or mt == self.ModelType.url:
                model_dict = {"type": None, "name": "", "url": m}
                if props:
                    model_dict.update(self.parse_model_props(props))
            else:
                raise CtbRecInvalidModelDefinition("Invalid model definition")
            payload_models.append(model_dict)

        return self.send_request("/rec", data={"action": "bulkStart", "models": payload_models})

    def update_model(self, model: Union[str, dict], props: dict) -> dict:
        """
        Update properties for an existing model on the server.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            props: Dict of one or more model definition items to update. These can include:
                   'priority' (int), 'suspended' (bool), 'bookmarked' (bool),
                   'recordUntil' (int|datetime), 'recordUntilSubsequentAction' (str),
                   'preferredResolution' (int), 'preferHigherBitrate' (bool),
                   'downtimeStart' (str HH:MM), 'downtimeEnd' (str HH:MM).
                   
        Returns:
            The updated model dict.
            
        Raises:
            CtbRecInvalidModelDefinition: If model format is not recognized.
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        props = self.parse_model_props(props)
        mt = self.parse_model_type(model)
        m = model if mt == self.ModelType.model_dict else self.find_model(model)
        invalid_keys = [k for k in props if k not in m]
        if invalid_keys:
            warnings.warn(f'Invalid properties {",".join(invalid_keys)} will be ignored.')
        p = {k: v for k, v in props.items() if k in m}
        if m and p:
            m.update(p)
            self.send_request("/rec", data={"action": "start", "model": m})
            return self.find_model(m)
        warnings.warn("Failed to update model properties")
        return dict()

    def update_model_properties(self, model: Union[str, dict], priority: int = None, 
                                 preferred_resolution: int = None, prefer_higher_bitrate: bool = None,
                                 downtime_start: str = None, downtime_end: str = None) -> dict:
        """
        Update specific properties for an existing model using the dedicated endpoint.
        
        This is more efficient than update_model() for updating resolution/priority settings
        as it uses a dedicated server action that triggers appropriate side effects.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            priority: New priority value (optional)
            preferred_resolution: Preferred resolution in pixels, e.g. 1080 (optional)
            prefer_higher_bitrate: Whether to prefer higher bitrate streams (optional)
            downtime_start: Start of downtime period in HH:MM format (optional)
            downtime_end: End of downtime period in HH:MM format (optional)
            
        Returns:
            Success message dict.
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        mt = self.parse_model_type(model)
        m = model if mt == self.ModelType.model_dict else self.find_model(model)
        
        model_data = {
            'url': m['url'],
            'priority': priority if priority is not None else m.get('priority', -1),
            'preferredResolution': preferred_resolution if preferred_resolution is not None else m.get('preferredResolution', -1),
            'preferHigherBitrate': prefer_higher_bitrate if prefer_higher_bitrate is not None else m.get('preferHigherBitrate', True),
            'downtimeStart': downtime_start if downtime_start is not None else m.get('downtimeStart', '00:00'),
            'downtimeEnd': downtime_end if downtime_end is not None else m.get('downtimeEnd', '00:00'),
        }
        
        return self.send_request("/rec", data={"action": "updateModelProperties", "model": model_data})

    def change_priority(self, model: Union[str, dict]) -> dict:
        """
        Notify the server that a model's priority has changed, triggering re-evaluation.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Returns:
            Success message dict.
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        mt = self.parse_model_type(model)
        m = model if mt == self.ModelType.model_dict else self.find_model(model)
        return self.send_request("/rec", data={"action": "changePriority", "model": m})

    def remove_model(self, model: Union[str, dict]):
        """
        Delete a model from recording list on the server.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecInvalidModelDefinition: If model format is not recognized.
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "stop", "model": self.find_model(model)})

    def remove_models(self, models: List[Union[str, dict]]) -> List[Union[str, dict]]:
        """
        Delete a list of models from the server, catching any exceptions.

        Args:
            models: List of models where elements must be one of [url[str], Site:Name[str], ModelDict[dict]]
            
        Returns:
            A list of any input models that failed to be removed.
        """
        failed = []
        for m in models:
            try:
                self.remove_model(m)
            except (CtbRecRequestFailed, CtbRecInvalidModelDefinition, CtbRecNotFound) as error:
                failed.append(m)
                warnings.warn(f'Unable to remove {m} from server: {error}')
        return failed

    def stop_model_at(self, model: Union[str, dict]):
        """
        Stop recording for a model at its scheduled recordUntil time.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "stopAt", "model": self.find_model(model)})

    def suspend_model(self, model: Union[str, dict]):
        """
        Suspend (pause) recording for a specific model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "suspend", "model": self.find_model(model)})

    def resume_model(self, model: Union[str, dict]):
        """
        Resume recording for a specific suspended model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "resume", "model": self.find_model(model)})

    def switch_resolution(self, model: Union[str, dict]):
        """
        Switch stream resolution for a model (triggers re-selection of stream source).

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "switch", "model": self.find_model(model)})

    def force_priority(self, model: Union[str, dict]):
        """
        Force recording for a model, ignoring priority/concurrent recording limits.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "forcePriority", "model": self.find_model(model)})

    def resume_priority(self, model: Union[str, dict]):
        """
        Resume respecting priority limits for a model (undo force_priority).

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "resumePriority", "model": self.find_model(model)})

    def mark_for_later(self, model: Union[str, dict]):
        """
        Bookmark a model for later recording (won't be recorded until unmarked).

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "markForLater", "model": self.find_model(model)})

    def unmark_for_later(self, model: Union[str, dict]):
        """
        Remove bookmark from a model (resume normal recording behavior).

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={"action": "unmarkForLater", "model": self.find_model(model)})

    def find_model(self, model: Union[str, dict]) -> dict:
        """
        Get an existing model on the server by matching model input.

        Args:
            model: String or dict - a ctbrec model definition
            
        Returns:
            Model dict if model found on server.
            
        Raises:
            CtbRecInvalidModelDefinition: If model format is not recognized.
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        models = self.get_models()
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            match = [m for m in models.values() if m['type'] == model['type'] and m['name'] == model['name']]
        elif mt == self.ModelType.url:
            match = [m for m in models.values() if self.url_match(m['url'], model)]
        elif mt == self.ModelType.site_name and model in models:
            match = [models[model]]
        else:
            match = []
        if match:
            return match[0]
        raise CtbRecNotFound("Requested model could not be found on server.")

    # ----------------------------------------- model import/export methods -------------------------------------------
    def export_models(self, stripped: bool = False) -> dict:
        """
        Export all models, notes, groups, and portraits from the server.

        Args:
            stripped: If True, key settings (resolution, bitrate, downtime) will be stripped.
            
        Returns:
            Dict containing models, notes, groups, and portraits.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        url = self.server_url + '/models/export'
        if stripped:
            url += '?stripped=true'
        result = self.session.get(
            url,
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return json.loads(result.text)
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def import_models(self, import_data: dict) -> dict:
        """
        Import models, notes, groups, and portraits to the server.

        Args:
            import_data: Dict containing models, notes, groups, and/or portraits to import.
            
        Returns:
            Response dict with status message.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        data_str = json.dumps(import_data)
        result = self.session.post(
            self.server_url + '/models/import',
            data=data_str,
            headers={'CTBREC-HMAC': self._compute_hmac(data_str)}
        )
        if result.status_code == 200:
            return json.loads(result.text)
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason} : {result.text}')

    # ----------------------------------------- model notes methods ----------------------------------------------------
    def get_model_notes(self) -> Dict[str, str]:
        """
        Get all model notes from the server.

        Returns:
            Dict mapping model URLs to their notes.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        result = self.session.get(
            self.server_url + '/models/notes/',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return json.loads(result.text)
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def get_model_note(self, model: Union[str, dict]) -> str:
        """
        Get the note for a specific model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Returns:
            The note text, or empty string if no note exists.
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            model_url = model['url']
        elif mt == self.ModelType.url:
            model_url = model
        else:
            m = self.find_model(model)
            model_url = m['url']
        
        encoded_url = quote(model_url, safe='')
        result = self.session.get(
            self.server_url + f'/models/notes/{encoded_url}',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return result.text
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def set_model_note(self, model: Union[str, dict], note: str):
        """
        Set or update the note for a specific model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            note: The note text to set.
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            model_url = model['url']
        elif mt == self.ModelType.url:
            model_url = model
        else:
            m = self.find_model(model)
            model_url = m['url']
        
        encoded_url = quote(model_url, safe='')
        result = self.session.post(
            self.server_url + f'/models/notes/{encoded_url}',
            data=note,
            headers={'CTBREC-HMAC': self._compute_hmac(note)}
        )
        if result.status_code != 200:
            raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def delete_model_note(self, model: Union[str, dict]):
        """
        Delete the note for a specific model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            model_url = model['url']
        elif mt == self.ModelType.url:
            model_url = model
        else:
            m = self.find_model(model)
            model_url = m['url']
        
        encoded_url = quote(model_url, safe='')
        result = self.session.delete(
            self.server_url + f'/models/notes/{encoded_url}',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code != 200:
            raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    # ----------------------------------------- model portrait/image methods -------------------------------------------
    def get_model_portrait(self, model: Union[str, dict]) -> Optional[bytes]:
        """
        Get the portrait image for a specific model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Returns:
            The portrait image as bytes (JPEG format), or None if no portrait exists.
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            model_url = model['url']
        elif mt == self.ModelType.url:
            model_url = model
        else:
            m = self.find_model(model)
            model_url = m['url']
        
        encoded_url = quote(model_url, safe='')
        result = self.session.get(
            self.server_url + f'/image/portrait/url/{encoded_url}',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return result.content
        elif result.status_code == 404:
            return None
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def set_model_portrait(self, model: Union[str, dict], image_data: bytes):
        """
        Set or update the portrait image for a specific model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            image_data: The portrait image as bytes (JPEG format recommended).
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
            
        Example:
            >>> with open('portrait.jpg', 'rb') as f:
            ...     ctb.set_model_portrait('Chaturbate:modelname', f.read())
        """
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            model_url = model['url']
        elif mt == self.ModelType.url:
            model_url = model
        else:
            m = self.find_model(model)
            model_url = m['url']
        
        encoded_url = quote(model_url, safe='')
        # Compute HMAC from binary data
        data_hmac = hmac.new(self.hmac_key, image_data, hashlib.sha256).hexdigest()
        result = self.session.post(
            self.server_url + f'/image/portrait/url/{encoded_url}',
            data=image_data,
            headers={
                'CTBREC-HMAC': data_hmac,
                'Content-Type': 'image/jpeg'
            }
        )
        if result.status_code != 200:
            raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def delete_model_portrait(self, model: Union[str, dict]):
        """
        Delete the portrait image for a specific model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            model_url = model['url']
        elif mt == self.ModelType.url:
            model_url = model
        else:
            m = self.find_model(model)
            model_url = m['url']
        
        encoded_url = quote(model_url, safe='')
        result = self.session.delete(
            self.server_url + f'/image/portrait/url/{encoded_url}',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code != 200:
            raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def get_portrait_by_id(self, portrait_id: str) -> Optional[bytes]:
        """
        Get a portrait image by its UUID.

        Args:
            portrait_id: The portrait UUID (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
            
        Returns:
            The portrait image as bytes (JPEG format), or None if not found.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        result = self.session.get(
            self.server_url + f'/image/portrait/{portrait_id}',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return result.content
        elif result.status_code == 404:
            return None
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def get_recording_thumbnail(self, filename: str) -> Optional[bytes]:
        """
        Get a recording thumbnail image.

        Args:
            filename: The relative path to the thumbnail within the recordings directory.
            
        Returns:
            The thumbnail image as bytes (JPEG format), or None if not found.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        result = self.session.get(
            self.server_url + f'/image/recording/{filename}',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return result.content
        elif result.status_code == 404:
            return None
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def save_model_portrait_to_file(self, model: Union[str, dict], filepath: str) -> bool:
        """
        Download and save a model's portrait to a file.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            filepath: Path where to save the image file.
            
        Returns:
            True if portrait was saved, False if no portrait exists.
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        portrait = self.get_model_portrait(model)
        if portrait:
            with open(filepath, 'wb') as f:
                f.write(portrait)
            return True
        return False

    def set_model_portrait_from_file(self, model: Union[str, dict], filepath: str):
        """
        Upload a portrait image from a file for a model.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            filepath: Path to the image file to upload.
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails.
            FileNotFoundError: If the specified file does not exist.
        """
        with open(filepath, 'rb') as f:
            image_data = f.read()
        self.set_model_portrait(model, image_data)

    def fetch_model_portrait_from_stream(self, model: Union[str, dict], preview: bool = False) -> bytes:
        """
        Fetch the current preview thumbnail from a model's live stream and save it as portrait.
        
        This method fetches the current preview image from the streaming site for the model,
        crops it to a square, scales it to 256x256 pixels, and saves it as the model's portrait.
        The model must be online for this to work on most sites.

        Args:
            model: One of [url[str], Site:Name[str], ModelDict[dict]]
            preview: If True, fetches the processed portrait image bytes without saving it on the server.
            
        Returns:
            The fetched and processed portrait image as bytes (JPEG format).
            
        Raises:
            CtbRecNotFound: If model could not be found.
            CtbRecRequestFailed: If the server request fails or preview is not available.
            
        Example:
            >>> portrait = ctb.fetch_model_portrait_from_stream('Chaturbate:modelname')
            >>> with open('portrait.jpg', 'wb') as f:
            ...     f.write(portrait)
        """
        mt = self.parse_model_type(model)
        if mt == self.ModelType.model_dict:
            model_url = model['url']
        elif mt == self.ModelType.url:
            model_url = model
        else:
            m = self.find_model(model)
            model_url = m['url']
        
        encoded_url = quote(model_url, safe='')
        url_path = f'/image/portrait/fetch/{encoded_url}'
        if preview:
            url_path += '?preview=true'
        result = self.session.get(
            self.server_url + url_path,
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return result.content
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.text}')

    def get_recording_contact_sheet(self, recording: dict) -> Optional[bytes]:
        """
        Get the contact sheet image for a recording.
        
        A contact sheet is a grid image showing frames from the recording,
        generated during post-processing if configured.

        Args:
            recording: The recording dict (must have 'absoluteFile' or path info).
            
        Returns:
            The contact sheet image as bytes (JPEG format), or None if not available.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
            
        Note:
            Contact sheets are typically named with a '.jpg' extension and stored
            alongside the recording file. The recording dict may contain the path
            in 'absoluteFile' or 'associatedFiles'.
        """
        # Try to find contact sheet path from recording
        contact_sheet_path = None
        
        # Check associatedFiles for .jpg files (contact sheets)
        associated = recording.get('associatedFiles', [])
        for f in associated:
            if f.lower().endswith('.jpg') and 'contact' not in f.lower():
                # Found a jpg that might be the contact sheet
                contact_sheet_path = f
                break
        
        # If we have absoluteFile, derive contact sheet path
        if not contact_sheet_path and recording.get('absoluteFile'):
            abs_file = recording['absoluteFile']
            # Contact sheet is typically the same name with .jpg extension
            if isinstance(abs_file, str):
                base_path = abs_file.rsplit('.', 1)[0] if '.' in abs_file else abs_file
                contact_sheet_path = base_path + '.jpg'
        
        if not contact_sheet_path:
            return None
        
        # Extract relative path from recordings directory
        # The server expects paths relative to the recordings directory
        return self.get_recording_thumbnail(contact_sheet_path)

    def save_recording_contact_sheet(self, recording: dict, filepath: str) -> bool:
        """
        Download and save a recording's contact sheet to a file.

        Args:
            recording: The recording dict.
            filepath: Path where to save the contact sheet image.
            
        Returns:
            True if contact sheet was saved, False if not available.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        contact_sheet = self.get_recording_contact_sheet(recording)
        if contact_sheet:
            with open(filepath, 'wb') as f:
                f.write(contact_sheet)
            return True
        return False

    # ----------------------------------------- model group methods ----------------------------------------------------
    def get_model_groups(self) -> Mapping[str, dict]:
        """
        Get a dict of all model groups currently on the server.

        Returns:
            Dict keyed by group-name, containing all model group dicts on the server. 
            Model groups contain keys ["name", "modelUrls", "id"].
        """
        g = self.send_request(url='/rec', data={'action': 'listModelGroups'})['groups']
        return {v['name']: v for v in g}

    def delete_model_group(self, group: Union[dict, str]):
        """
        Delete a model group from the server.

        Args:
            group: A group dict, or group name identifying the group to be deleted.
            
        Raises:
            CtbRecNotFound: If group could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        if isinstance(group, str):
            g = self.find_model_group(group)
        else:
            g = group
        self.send_request(url='/rec', data={'action': 'deleteModelGroup', 'modelGroup': g})

    def save_model_group(self, group: dict):
        """
        Save a model group to the server. This will overwrite any existing information in the group.

        Args:
            group: The group dict to be saved.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'saveModelGroup', 'modelGroup': group})

    def add_models_to_group(self, group: Union[dict, str], model_list: List[Union[dict, str]]) -> dict:
        """
        Add models to an existing model group.

        Args:
            group: Either a group name or a group dict, specifying an existing model group.
            model_list: A list of models where list items can be either a URL string, or a model dict.
            
        Returns:
            The updated model group retrieved back from the server.
            
        Raises:
            CtbRecNotFound: If group could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        if isinstance(group, str):
            group = self.find_model_group(group)
        ml = {m if isinstance(m, str) else m['url'] for m in model_list}
        group['modelUrls'].extend(list(ml))
        self.save_model_group(group)
        return self.get_model_groups()[group['name']]

    def remove_models_from_group(self, group: Union[dict, str], model_list: List[Union[dict, str]]) -> dict:
        """
        Remove models from an existing model group.

        Args:
            group: Either a group name or a group dict, specifying an existing model group.
            model_list: A list of models where list items can be either a URL string, or a model dict.
            
        Returns:
            The updated model group retrieved back from the server.
            
        Raises:
            CtbRecNotFound: If group could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        if isinstance(group, str):
            group = self.find_model_group(group)
        ml = {m if isinstance(m, str) else m['url'] for m in model_list}
        group['modelUrls'] = [m for m in group['modelUrls'] if m not in ml]
        self.save_model_group(group)
        return self.get_model_groups()[group['name']]

    def create_model_group(self, name: str, model_list: list) -> dict:
        """
        Create a new model group on the server.

        Args:
            name: A string specifying name of the new group. Must be unique.
            model_list: A list of models where list items can be either a URL string, or a model dict.
            
        Returns:
            The created model group dict.
            
        Raises:
            CtbRecAlreadyExists: If a group with that name already exists.
            CtbRecRequestFailed: If the server request fails.
        """
        groups = self.get_model_groups()
        if name in groups:
            raise CtbRecAlreadyExists(f'Model group {name} already exists')
        ml = {m if isinstance(m, str) else m['url'] for m in model_list}  # use set to reduce to unique urls
        self.save_model_group({"name": name, 'modelUrls': list(ml), 'id': uuid.uuid4().__str__()})
        return self.get_model_groups()[name]

    def find_model_group(self, name: str) -> dict:
        """
        Retrieve an existing model group from the server by name.

        Args:
            name: A string specifying name of the group.
            
        Returns:
            Model-group dict.
            
        Raises:
            CtbRecNotFound: If group could not be found.
            CtbRecRequestFailed: If the server request fails.
        """
        groups = self.get_model_groups()
        if name in groups:
            return groups[name]
        raise CtbRecNotFound(f'Model group {name} could not be found on the server')

    # --------------------------------------- recording methods -------------------------------------------------------
    def get_recordings(self) -> List[dict]:
        """
        Get a list of all recordings from the server.

        Returns:
            List of recording dicts.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        return self.send_request(url='/rec', data={'action': 'recordings'})['recordings']

    def delete_recording(self, recording: dict):
        """
        **Permanently** delete a recording on server.

        Args:
            recording: The recording dict to delete.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'delete', 'recording': recording})

    def pin_recording(self, recording: dict):
        """
        Pin a recording on the server (prevents automatic deletion).

        Args:
            recording: The recording dict to pin.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'pin', 'recording': recording})

    def unpin_recording(self, recording: dict):
        """
        Unpin a recording on the server.

        Args:
            recording: The recording dict to unpin.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'unpin', 'recording': recording})

    def annotate_recording(self, recording: dict, note: str):
        """
        Add a note to a recording on the server.

        Args:
            recording: The recording dict to annotate.
            note: The note text to add.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        recording['note'] = note
        self.send_request(url='/rec', data={'action': 'setNote', 'recording': recording})

    def rerun_post_process(self, recording: dict):
        """
        Rerun post-processing for a recording.

        Args:
            recording: The recording dict to reprocess.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'rerunPostProcessing', 'recording': recording})

    # --------------------------------------- general server methods ---------------------------------------------------
    def get_settings(self) -> list:
        """
        Get current server settings.

        Returns:
            List of current server settings. Each item is a dict with keys: 
            'key', 'name', 'type', 'value'.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        return self.send_request(url='/config')

    def update_settings(self, settings: Union[dict, list]) -> list:
        """
        Update server config settings.

        Args:
            settings: Either a dict of key-value pairs where keys must be valid ctbrec setting keys 
                      and values must conform to expected type, or a list of ctbrec settings.
                      
        Returns:
            List of server settings after updates have been applied.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        if isinstance(settings, dict):
            data = {s['key']: s for s in self.get_settings()}
            for k in settings:
                if k not in data.keys():
                    warnings.warn(f'{k} is not a valid settings key and will be ignored')
                else:
                    data[k]['value'] = settings[k]
            data = list(data.values())
        else:
            data = settings
        self.send_request(url='/config', data=data)
        return self.get_settings()

    def get_raw_config(self) -> dict:
        """
        Get the raw server.json config file content.

        Returns:
            Dict containing the raw server configuration.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        result = self.session.get(
            self.server_url + '/config?action=raw',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return json.loads(result.text)
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def set_raw_config(self, config: dict) -> dict:
        """
        Set the raw server.json config file content.
        
        Warning: Some changes may require a server restart to take effect.

        Args:
            config: Dict containing the new server configuration.
            
        Returns:
            Response dict with status message.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        config_str = json.dumps(config)
        result = self.session.post(
            self.server_url + '/config?action=raw',
            data=config_str,
            headers={'CTBREC-HMAC': self._compute_hmac(config_str)}
        )
        if result.status_code == 200:
            return json.loads(result.text)
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason} : {result.text}')

    def get_space(self) -> dict:
        """
        Get drive space statistics from server.

        Returns:
            Dict of drive space statistics including:
            - spaceTotal: Total space in bytes
            - spaceFree: Free space in bytes
            - throughput: Current throughput in bytes/sec
            - throughputTimeframe: Timeframe for throughput measurement in ms
            - minimumSpaceLeftInBytes: Configured minimum free space
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        return self.send_request(url='/rec', data={'action': 'space'})

    def get_recorder_status(self) -> dict:
        """
        Get the current recorder status.

        Returns:
            Dict with 'status' and 'paused' keys indicating if recorder is paused.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        return self.send_request(url='/rec', data={'action': 'recorderStatus'})

    def get_summary(self) -> dict:
        """
        Get summary of server activity.

        Returns:
            Dict containing:
            - total_models: Total number of models
            - models_recording: Number currently recording
            - models_online: Number currently online
            - models_paused: Number of paused models
            - models_marked_later: Number bookmarked for later
            - total_recordings: Total recording count
            - post_processing: Number in post-processing
            - space_used: Used space as formatted string
            - space_free: Free space as formatted string
            - throughput: Current throughput as formatted string
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        models = self.get_models()
        paused = len([m for m in models.values() if m['suspended']])
        later = len([m for m in models.values() if m.get('bookmarked', m.get('markedForLater', False))])
        online = len(self.get_models(online=True))
        recordings = self.get_recordings()
        recording = len([r for r in recordings if r['status'] == 'RECORDING'])
        post_process = len([r for r in recordings if r['status'] == 'POST_PROCESSING'])
        space = self.get_space()
        throughput = space.get('throughput', 0)
        return {
            "total_models": len(models),
            "models_recording": recording,
            "models_online": online,
            "models_paused": paused,
            "models_marked_later": later,
            "total_recordings": len(recordings),
            "post_processing": post_process,
            "space_used": f"{round((space['spaceTotal'] - space['spaceFree']) / 1e9, 3)} GB",
            "space_free": f"{round(space['spaceFree'] / 1e9, 3)} GB",
            "throughput": f"{round(throughput / 1e6, 2)} MB/s" if throughput > 0 else "0 MB/s"
        }

    def pause_recording(self):
        """
        Suspend all recording on the server (pauses all non-bookmarked models).

        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'pauseRecorder'})

    def resume_recording(self):
        """
        Resume all recording on the server.

        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'resumeRecorder'})

    def clean_metadata(self):
        """
        Clean orphaned recording metadata from the server.
        
        This removes metadata files for recordings where the actual 
        recording files no longer exist.

        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'cleanMetadata'})

    def get_corrupt_metadata(self) -> List[str]:
        """
        Get a list of all corrupt recording metadata files on the server.

        Returns:
            List of filenames.

        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        return self.send_request(url='/rec', data={'action': 'listCorruptMetadata'})['files']

    def scan_corrupt_metadata(self) -> List[str]:
        """
        Rescan recording metadata and return corrupt metadata files.

        Returns:
            List of filenames.

        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        return self.send_request(url='/rec', data={'action': 'scanCorruptMetadata'})['files']

    def delete_corrupt_metadata(self, filename: str):
        """
        Delete a corrupt recording metadata file from the server.

        Args:
            filename: The name of the corrupt file to delete.

        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        self.send_request(url='/rec', data={'action': 'deleteCorruptMetadata', 'file': filename})

    def get_debug_stats(self) -> str:
        """
        Get debug statistics from the server (requires debug endpoint to be enabled).

        Returns:
            HTML string containing debug statistics.
            
        Raises:
            CtbRecRequestFailed: If the server request fails or endpoint not available.
        """
        result = self.session.get(self.server_url + '/debug/stats')
        if result.status_code == 200:
            return result.text
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    def get_debug_stack(self) -> str:
        """
        Get all thread stack traces from the server.

        Returns:
            Plain text string containing thread stack traces.
            
        Raises:
            CtbRecRequestFailed: If the server request fails.
        """
        result = self.session.get(
            self.server_url + '/debug/stack/',
            headers={'CTBREC-HMAC': self._compute_hmac('')}
        )
        if result.status_code == 200:
            return result.text
        raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason}')

    # ------------------------------------------- internal methods -----------------------------------------------------
    def type_to_site(self, model_type: str) -> str:
        """
        Get ctbrec site code from ctbrec site class name.

        Args:
            model_type: String containing ctbrec model type code.
            
        Returns:
            Site name extracted from model type.
        """
        return re.findall(self.regex['model_type'], model_type)[0]

    def parse_model_props(self, props: dict) -> dict:
        """
        Process model properties. Handles datetime conversion for recordUntil field.

        Args:
            props: Dict containing model properties.
            
        Returns:
            Model dict after converting recordUntil to a timestamp.
        """
        p = props.copy()
        if p and 'recordUntil' in p:
            record_until = p['recordUntil']
            if isinstance(record_until, datetime):
                p['recordUntil'] = round(record_until.timestamp() * 1000)
            elif isinstance(record_until, int) and record_until < 10000:   # assume it is specified in hours
                p['recordUntil'] = round(datetime.now().timestamp() * 1000 + record_until * 3600000)
        return p

    def model_id(self, model: dict) -> str:
        """
        Get model id from model dict. Id is Site:ModelName.

        Args:
            model: ctbrec model dict.
            
        Returns:
            String in format "Site:ModelName".
        """
        return re.findall(self.regex['model_type'], model['type'])[0] + ':' + model['name']

    def url_match(self, url1: str, url2: str) -> bool:
        """
        Check if two URLs match, either exact match or by top level domain and name.

        This makes the assumption that model name is the last string in the URL, 
        which seems to be the case at the moment - may not always be true in the future.
        """
        u1 = url1.strip().rstrip('/')
        u2 = url2.strip().rstrip('/')
        if u1 == u2:
            return True
        try:
            u1g = re.findall(self.regex['domain_name'], u1)[0]
            u2g = re.findall(self.regex['domain_name'], u2)[0]
            return u1g[1] == u2g[1] and u1g[3] == u2g[3]
        except IndexError:
            return False

    def parse_model_type(self, model: Union[str, dict]) -> 'CtbRec.ModelType':
        """
        Determine model request type from model input.
        
        Args:
            model: Model specification (URL string, Site:Name string, or model dict).
            
        Returns:
            ModelType enum value.
            
        Raises:
            CtbRecInvalidModelDefinition: If model format is not recognized.
        """
        if isinstance(model, dict) and all(k in model for k in ['type', 'name', 'url']):
            return self.ModelType.model_dict
        elif isinstance(model, str) and re.match(self.regex['url'], model):
            return self.ModelType.url
        elif isinstance(model, str) and re.match(self.regex['site_name'], model):
            return self.ModelType.site_name
        raise CtbRecInvalidModelDefinition("Model must be one of [url[str], Site:Name[str], ModelDict[dict]]")

    def _compute_hmac(self, data: str) -> str:
        """Compute HMAC for request authentication."""
        return hmac.new(self.hmac_key, data.encode('utf-8'), hashlib.sha256).hexdigest()

    def send_request(self, url: str, data: Optional[Union[dict, list]] = None) -> Union[dict, list]:
        """
        Send a request to the ctbrec server.

        Args:
            url: Relative URL for the request, e.g. '/rec'.
            data: Payload to send to server. If None then GET will be used rather than POST.
            
        Returns:
            Server result data structure.
            
        Raises:
            CtbRecRequestFailed: If the request fails or server returns an error.
        """
        data_str = '' if data is None else json.dumps(data)
        data_hmac = hmac.new(self.hmac_key, data_str.encode('utf-8'), hashlib.sha256).hexdigest()
        self.session.headers.update({'CTBREC-HMAC': data_hmac})
        if data is None:
            result = self.session.get(self.server_url + url)
        else:
            result = self.session.post(self.server_url + url, data=data_str)
        if result.status_code == 200:
            result_json = json.loads(result.text)
            if isinstance(result_json, dict) and result_json.get('status') not in (None, "success"):
                raise CtbRecRequestFailed(f"Request failed: {result_json.get('msg', 'Unknown error')}")
            else:
                return result_json
        else:
            raise CtbRecRequestFailed(f'HTTP error: {result.status_code} : {result.reason} : {result.text}')
