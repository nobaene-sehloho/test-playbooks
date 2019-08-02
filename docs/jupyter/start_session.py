import os

from awxkit import api, config, utils

def start_session():
    if os.getenv('AWXKIT_CREDENTIAL_FILE'):
        config.credentials = utils.load_credentials(os.getenv('AWXKIT_CREDENTIAL_FILE', 'config/credentials.yml'))
    else:
        config.credentials = utils.PseudoNamespace({'default': {'username': os.getenv('AWXKIT_USER', 'admin'),
                                                                'password': os.getenv('AWXKIT_USER_PASSWORD', 'password'),
                                                                'base_url': os.getenv('AWX_URL', 'https://127.0.0.1:8043')
                                                                }
                                                            }
                                                        )
    root = api.Api()
    config.use_sessions = True
    root.load_session().get()

    v2 = root.available_versions.v2.get()
    return root, v2
