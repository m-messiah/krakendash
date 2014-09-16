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


from subprocess import check_output
import json

from django.shortcuts import render_to_response
from django.shortcuts import render
from django.shortcuts import redirect


def param(request, key):
    if key not in request.GET:
        raise Exception(key + "not found in request")
    return escape(request.GET[key])


def escape(s):
    return s.replace("'", "'\\''").replace("#", "'\\#'").replace("&", "'\\&'")


def ops(request):
    users_list = json.loads(check_output(["radosgw-admin", "metadata",
                                          "list", "user"]))
    users = {}
    for username in users_list:
        users[username] = json.loads(
            check_output(["radosgw-admin", "user", "info",
                          "--uid={0}".format(username)]))
    return render(request, 'ops.html', locals())


def user_custom(request, user, func, argument):
    if func:
        func = func[1:]
    else:
        users = {user: json.loads(
            check_output(["radosgw-admin", "user", "info",
                          "--uid={0}".format(user)]))}
        return render_to_response('ops.html', locals())
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
            res = check_output(["radosgw-admin", "user", "create",
                                "--uid={0}".format(uid),
                                "--display-name={0}".format(name),
                                "--email={0}".format(email)])

    elif func == "suspend":
        if int(argument) > 0:
            res = check_output(["radosgw-admin", "user", "enable",
                                "--uid={0}".format(escape(user))])
        else:
            res = check_output(["radosgw-admin", "user", "suspend",
                                "--uid={0}".format(escape(user))])

    elif func == "newkey":
        res = check_output(["radosgw-admin", "user", "modify",
                            "--uid={0}".format(escape(user)),
                            "--gen-access-key"])

    elif func == "deletekey":
        res = check_output(["radosgw-admin", "key", "rm",
                            "--uid={0}".format(escape(user)),
                            "--access-key={0}".format(escape(argument))])

    elif func == "customize":
        try:
            user_info = json.loads(
                check_output(["radosgw-admin", "user", "info",
                              "--uid={0}".format(escape(user))]))
            command = ["radosgw-admin", "user", "modify",
                       "--uid={0}".format(escape(user))]

            email = param(request, 'email')
            name = param(request, 'name')
            maxbuckets = param(request, 'maxbuckets')
            maxobjects = param(request, 'maxobjects')
            maxsizekb = int(param(request, 'maxsizekb'))
            maxbuckobjects = param(request, 'maxbuckobjects')
            maxbucksizekb = int(param(request, 'maxbucksizekb'))
            if email != user_info["email"]:
                command.append("--email={0}".format(email))
            if name != user_info["display_name"]:
                command.append("--display_name={0}".format(name))

            if len(command) > 4:
                res = check_output(command)

            command = ["radosgw-admin", "quota", "set",
                       "--uid={0}".format(escape(user)),
                       "--quota-scope=user"]

            if maxobjects != user_info["user_quota"]["max_objects"]:
                command.append("--max-objects={0}".format(maxobjects))

            if maxsizekb != int(user_info["user_quota"]["max_size_kb"]):
                if maxsizekb > 0:
                    maxsizekb *= 1024
                command.append("--max-size={0}".format(maxsizekb))

            if len(command) > 5:
                res = check_output(command)
                res = check_output(["radosgw-admin", "quota", "enable",
                                    "--quota-scope=user",
                                    "--uid={0}".format(escape(user))])
            if (int(maxobjects) == maxsizekb) and maxsizekb < 0:
                res = check_output(["radosgw-admin", "quota", "disable",
                                    "--quota-scope=user",
                                    "--uid={0}".format(escape(user))])

            command = ["radosgw-admin", "quota", "set",
                       "--uid={0}".format(escape(user)),
                       "--quota-scope=bucket"]

            if maxbuckobjects != user_info["bucket_quota"]["max_objects"]:
                command.append("--max-objects={0}".format(maxbuckobjects))

            if maxbucksizekb != int(user_info["bucket_quota"]["max_size_kb"]):
                if maxbucksizekb > 0:
                    maxbucksizekb *= 1024
                command.append("--max-size={0}".format(maxbucksizekb))

            if len(command) > 5:
                res = check_output(command)
                res = check_output(["radosgw-admin", "quota", "enable",
                                    "--quota-scope=bucket",
                                    "--uid={0}".format(escape(user))])

            if (int(maxbuckobjects) == maxbucksizekb) and maxbucksizekb < 0:
                res = check_output(["radosgw-admin", "quota", "disable",
                                    "--quota-scope=bucket",
                                    "--uid={0}".format(escape(user))])

        except Exception as e:
            error = e
            return render(request, "ops.html", locals())

    return redirect("/krakendash/ops/")