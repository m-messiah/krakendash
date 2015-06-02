from django.conf.urls import patterns, include, url
from django.contrib.auth.views import login, logout
from api import views


base_urlpatterns = patterns(
    '',
    url(r'^$', 'status.views.home', name='home'),
    url(r'^ops/$', 'ops.views.ops', name='ops'),
    url(r'^osd/(\d+)/$', 'status.views.osd_details', name='osd_details'),
    url(r'^activity/$', 'status.views.activity', name='activity'),
    url(r'^user/(.+?)(/.+?)?(/.+?)?/$', 'ops.views.user_custom',
        name='user_custom'),
    url(r'^api/clusters/health/$', views.health, name="cluster-health"),
    url(r'^api/clusters/status/$', views.status, name="cluster-status"),
    url(r'^api/clusters/overview/$', views.overview, name="cluster-status"),
    url(r'^api/clusters/$', views.clusters, name="clusters"),
    url(r'^api/$', views.api, name="api"),
)

urlpatterns = patterns('',
    url(r'krakendash/', include(base_urlpatterns)),
)
