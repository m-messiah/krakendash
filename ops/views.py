# Copyright (c) 2013,2014 Donald Talton
# All rights reserved.

# Redistribution and use in source and binary forms,
# with or without modification,
# are permitted provided that the following conditions are met:

# Redistributions of source code must retain the above copyright notice, this
#  list of conditions and the following disclaimer.

# Redistributions in binary form must reproduce the above copyright notice, this
#  list of conditions and the following disclaimer in the documentation and/or
#  other materials provided with the distribution.

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
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from subprocess import check_output
import json

from django.shortcuts import render_to_response
from django.shortcuts import render
from django.shortcuts import redirect


def param(request, key):
    return key in request.GET


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
        if (param(request, 'newUid') and
                param(request, 'newName') and
                param(request, 'newEmail')):
            uid = request.GET['newUid']
            name = request.GET['newName']
            email = request.GET['newEmail']

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
        pass
    return redirect("/krakendash/ops/")