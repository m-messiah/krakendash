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


import json
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import render
from django.shortcuts import redirect
from rgwadmin import RGWAdmin

rgwAdmin = RGWAdmin(settings.S3_ACCESS, settings.S3_SECRET,
                    settings.S3_SERVER, secure=False)


def param(request, key):
    if key not in request.GET:
        raise Exception(key + "not found in request")
    return request.GET[key]


def get_user_info(username):
    userinfo = rgwAdmin.get_user(username)
    userinfo.update({"user_quota": rgwAdmin.get_quota(username, "user"),
                     "bucket_quota": rgwAdmin.get_quota(username, "bucket")})
    return userinfo


def ops(request):
    users = {username: get_user_info(username)
             for username in rgwAdmin.get_users()}
    return render(request, 'ops.html', locals())


def user_custom(request, user, func, argument):
    if func:
        func = func[1:]
    else:
        return ops(request)

    if argument:
        argument = argument[1:]

    if user == "0" and func == "adduser":
        try:
            uid = param(request, 'newUid')
            name = param(request, 'newName')
            email = param(request, 'newEmail')
        except Exception as e:
            error = e
        else:
            res = rgwAdmin.create_user(uid, name, email)
            return render(request, "user.html", {"username": uid,
                                                 "stats": res,
                                                 "new": True})

    elif func == "suspend":
        if int(argument) > 0:
            res = rgwAdmin.modify_user(user, generate_key=False)
        else:
            res = rgwAdmin.modify_user(user, generate_key=False,
                                       suspended=True)

    elif func == "addkey":
        old = rgwAdmin.get_user(user)["keys"]
        res = rgwAdmin.create_key(user)
        newkey = [item for item in res if item not in old][0]
        return HttpResponse(json.dumps(newkey),
                            content_type='application/json')

    elif func == "customize":
        try:
            p_name, p_email, p_maxbuckets = None, None, None
            p_maxobjects, p_maxsizekb = None, None
            user_info = get_user_info(user)
            suspended = user_info["suspended"]
            email = param(request, 'email')
            name = param(request, 'name')
            maxbuckets = int(param(request, 'maxbuckets'))
            maxobjects = int(param(request, 'maxobjects'))
            maxsizekb = int(param(request, 'maxsizekb'))
            maxbuckobjects = int(param(request, 'maxbuckobjects'))
            maxbucksizekb = int(param(request, 'maxbucksizekb'))

            # Change name, email, max buckets
            if email != user_info["email"]:
                p_email = email
            if name != user_info["display_name"]:
                p_name = name
            if maxbuckets != user_info["max_buckets"]:
                p_maxbuckets = maxbuckets

            res = rgwAdmin.modify_user(user, p_name, p_email,
                                       max_buckets=p_maxbuckets,
                                       generate_key=False,
                                       suspended=suspended)

            # Change user quota
            if maxobjects != user_info["user_quota"]["max_objects"]:
                p_maxobjects = maxobjects

            if maxsizekb != int(user_info["user_quota"]["max_size_kb"]):
                p_maxsizekb = maxsizekb

            res = rgwAdmin.set_quota(
                user, "user", p_maxsizekb, p_maxobjects,
                enabled=(maxobjects > -1 or maxsizekb > -1))

            # Change bucket quota
            p_maxobjects, p_maxsizekb = None, None
            if maxbuckobjects != user_info["bucket_quota"]["max_objects"]:
                p_maxobjects = maxbuckobjects

            if maxbucksizekb != int(user_info["bucket_quota"]["max_size_kb"]):
                p_maxsizekb = maxbucksizekb

            res = rgwAdmin.set_quota(
                user, "bucket", p_maxsizekb, p_maxobjects,
                enabled=(maxbuckobjects > -1 or maxbucksizekb > -1))

        except Exception as e:
            error = e
            return render(request, "ops.html", locals())

    return redirect("/krakendash/ops/")
