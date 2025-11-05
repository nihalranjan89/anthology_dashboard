from django.utils.deprecation import MiddlewareMixin

class DisableBrowserCacheMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        print("Cache control middleware active ✅")
        return response
