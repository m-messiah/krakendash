# Copyright (c) 2013,2014 Donald Talton
# All rights reserved.

# Redistribution and use in source and binary forms,
# with or without modification,
# are permitted provided that the following conditions are met:

# Redistributions of source code must retain the above copyright notice, this
#  list of conditions and the following disclaimer.

# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.

# Neither the name of Donald Talton nor the names of its
#  contributors may be used to endorse or promote products derived from
#  this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import render
from django.shortcuts import redirect
from rgwadmin import RGWAdmin

s3_servers = list(settings.S3_SERVERS)
rgwAdmin = RGWAdmin(settings.S3_ACCESS, settings.S3_SECRET,
                    s3_servers.pop(0), secure=False)


def param(request, key):
    if key not in request.GET:
        raise Exception(key + "not found in request")
    return request.GET[key]


def get_user_info(username, public=False):
    userinfo = rgwAdmin.get_user(username)
    userinfo.update({"user_quota": rgwAdmin.get_quota(username, "user"),
                     "bucket_quota": rgwAdmin.get_quota(username, "bucket")})
    if public:
        map(lambda d: d.pop("secret_key"), userinfo["keys"])
        map(lambda d: d.pop("secret_key"), userinfo["swift_keys"])
    return userinfo


def ops(request):
    users = {username: get_user_info(username, public=True)
             for username in rgwAdmin.get_users()}
    if 'json' in request.GET:
        return JsonResponse({"users": users})
    else:
        return render(request, 'ops.html', {"users": users})


def user_custom(request, user, func, argument):
    if func:
        func = func[1:]
    else:
        return ops(request)

    if argument:
        argument = argument[1:]

    def adduser(r, u, _):
        if u != "0":
            return redirect("/krakendash/ops/")
        try:
            uid = param(r, 'newUid')
            name = param(r, 'newName')
            email = param(r, 'newEmail')
        except Exception as e:
            return render(r, 'ops.html', {"error": e})
        else:
            res = rgwAdmin.create_user(uid, name, email)
            return render(r, "user.html", {"username": uid,
                                           "stats": res,
                                           "new": True})

    def suspend(_, u, arg):
        if int(arg) > 0:
            rgwAdmin.modify_user(u, generate_key=False)
        else:
            rgwAdmin.modify_user(u, generate_key=False, suspended=True)
        return redirect("/krakendash/ops/")

    def addkey(_, u, __):
        old = rgwAdmin.get_user(u)["keys"]
        res = rgwAdmin.create_key(u)
        newkey = [item for item in res if item not in old][0]
        return JsonResponse(newkey)

    def subuser(r, req_user, _):
        user_info = get_user_info(req_user)
        sub_user = param(r, "subuser_name")
        if req_user in sub_user:
            if sub_user not in [u["id"] for u in user_info["subusers"]]:
                rgwAdmin.create_subuser(
                    req_user, subuser=sub_user,
                    key_type='swift', access='full',
                    generate_secret=True)
                user_info = get_user_info(req_user)
                for key in user_info["swift_keys"]:
                    if key["user"] == sub_user:
                            return JsonResponse(key)
                error = "Key not added"
            else:
                error = "User exists"
        else:
            error = "Swift must be \"" + req_user + ":[a-z0-9]\""
        return JsonResponse({"user": "Error", "secret_key": error})

    def customize(r, req_user, _):
        try:
            (p_name, p_email, p_maxbuckets,
             p_subuser, p_maxobjects, p_maxsizekb) = [None] * 6
            user_info = get_user_info(req_user)
            suspended = user_info["suspended"]
            email = param(r, 'email')
            name = param(r, 'name')
            sub_user = param(r, "subuser")
            maxbuckets = int(param(r, 'maxbuckets'))
            maxobjects = int(param(r, 'maxobjects'))
            maxsizekb = int(param(r, 'maxsizekb'))
            maxbuckobjects = int(param(r, 'maxbuckobjects'))
            maxbucksizekb = int(param(r, 'maxbucksizekb'))

            # Change name, email, max buckets
            if email != user_info["email"]:
                p_email = email
            if name != user_info["display_name"]:
                p_name = name
            if maxbuckets != user_info["max_buckets"]:
                p_maxbuckets = maxbuckets

            rgwAdmin.modify_user(req_user, p_name, p_email,
                                 max_buckets=p_maxbuckets,
                                 generate_key=False,
                                 suspended=suspended)

            # Change user quota
            if maxobjects != user_info["user_quota"]["max_objects"]:
                p_maxobjects = maxobjects

            if maxsizekb != int(user_info["user_quota"]["max_size_kb"]):
                p_maxsizekb = maxsizekb

            rgwAdmin.set_quota(
                req_user, "user", p_maxsizekb, p_maxobjects,
                enabled=(maxobjects > -1 or maxsizekb > -1))

            # Change bucket quota
            p_maxobjects, p_maxsizekb = None, None
            if maxbuckobjects != user_info["bucket_quota"]["max_objects"]:
                p_maxobjects = maxbuckobjects

            if maxbucksizekb != int(user_info["bucket_quota"]["max_size_kb"]):
                p_maxsizekb = maxbucksizekb

            rgwAdmin.set_quota(
                req_user, "bucket", p_maxsizekb, p_maxobjects,
                enabled=(maxbuckobjects > -1 or maxbucksizekb > -1))

        except Exception as e:
            return render(r, "ops.html", {"error": e})

    return {"adduser": adduser,
            "suspend": suspend,
            "addkey": addkey,
            "subuser": subuser,
            "customize": customize
            }.get(func, redirect("/krakendash/ops/"))(request, user, argument)
