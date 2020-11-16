from filebase_api import fapi_remote, FilebaseApiPage


@fapi_remote
def oauth_authenticate(page: FilebaseApiPage, provider_name):
    raise NotImplementedError("Not yet implemented")


@fapi_remote
def oauth_get_providers(page: FilebaseApiPage):
    provider_infos = {}
    for provider in page.api_config.oauth_providers:
        client = page.oauth_client_from_provider(provider)
        provider_infos[provider] = {
            "authorize_url": client.get_authorize_url(),
        }
    return provider_infos
