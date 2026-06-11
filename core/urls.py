from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.views.generic import TemplateView

schema_view = get_schema_view(
   openapi.Info(
      title="Fuel API",
      default_version='v1',
      description="Fuel API description",
      terms_of_service="https://terms",
      contact=openapi.Contact(email="contact@fuelapi.com"),
      license=openapi.License(name="Fuel API"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)
urlpatterns = [
    path('api/', include('api.urls')),
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

urlpatterns += [path('', TemplateView.as_view(template_name='index.html'), name='demo')]
