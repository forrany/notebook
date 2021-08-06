"""Tornado handlers for the contents web service.

Preliminary documentation at https://github.com/ipython/ipython/wiki/IPEP-27%3A-Contents-Service
"""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import json
import os
import time
from shutil import copyfile
from subprocess import check_call

from git import Repo
from notebook.services.constants import (
    SUCCESS_CODE,
    DELIMITER,
    RESPONSE_MESSAGE,
    BK_USERNAME_NULL_CODE,
    GIT_COMMAND_CODE,
    SPECIAL_CHAR_CODE,
    EXAMPLE_NB,
    MLSQL_NB,
    DELETE_TAG,
    VERSION_EXIST_CODE,
    VERSION_NULL_CODE,
)
from tornado import gen, web

from notebook.services.pizza_api import check_project_auth, generate_response
from notebook.utils import maybe_future, url_path_join, url_escape
from jupyter_client.jsonutil import date_default

from notebook.base.handlers import (
    IPythonHandler, APIHandler, path_regex,
)


def validate_model(model, expect_content):
    """
    Validate a model returned by a ContentsManager method.

    If expect_content is True, then we expect non-null entries for 'content'
    and 'format'.
    """
    required_keys = {
        "name",
        "path",
        "type",
        "writable",
        "created",
        "last_modified",
        "mimetype",
        "content",
        "format",
    }
    missing = required_keys - set(model.keys())
    if missing:
        raise web.HTTPError(
            500,
            u"Missing Model Keys: {missing}".format(missing=missing),
        )

    maybe_none_keys = ['content', 'format']
    if expect_content:
        errors = [key for key in maybe_none_keys if model[key] is None]
        if errors:
            raise web.HTTPError(
                500,
                u"Keys unexpectedly None: {keys}".format(keys=errors),
            )
    else:
        errors = {
            key: model[key]
            for key in maybe_none_keys
            if model[key] is not None
        }
        if errors:
            raise web.HTTPError(
                500,
                u"Keys unexpectedly not None: {keys}".format(keys=errors),
            )


class ContentsHandler(APIHandler):

    def location_url(self, path):
        """Return the full URL location of a file.

        Parameters
        ----------
        path : unicode
            The API path of the file, such as "foo/bar.txt".
        """
        return url_path_join(
            self.base_url, 'api', 'contents', url_escape(path)
        )

    def _finish_model(self, model, location=True):
        """Finish a JSON request with a model, setting relevant headers, etc."""
        if location:
            location = self.location_url(model['path'])
            self.set_header('Location', location)
        self.set_header('Last-Modified', model['last_modified'])
        self.set_header('Content-Type', 'application/json')
        self.finish(json.dumps(model, default=date_default))

    @web.authenticated
    @gen.coroutine
    def get(self, path=''):
        """Return a model for a file or directory.

        A directory model contains a list of models (without content)
        of the files and directories it contains.
        """
        path = path or ''
        type = self.get_query_argument('type', default=None)
        if type not in {None, 'directory', 'file', 'notebook'}:
            raise web.HTTPError(400, u'Type %r is invalid' % type)

        format = self.get_query_argument('format', default=None)
        if format not in {None, 'text', 'base64'}:
            raise web.HTTPError(400, u'Format %r is invalid' % format)
        content = self.get_query_argument('content', default='1')
        if content not in {'0', '1'}:
            raise web.HTTPError(400, u'Content %r is invalid' % content)
        content = int(content)

        model = yield maybe_future(self.contents_manager.get(
            path=path, type=type, format=format, content=content,
        ))
        validate_model(model, expect_content=content)
        self._finish_model(model, location=False)

    @web.authenticated
    @gen.coroutine
    def patch(self, path=''):
        """PATCH renames a file or directory without re-uploading content."""
        cm = self.contents_manager
        model = self.get_json_body()
        if model is None:
            raise web.HTTPError(400, u'JSON body missing')
        model = yield maybe_future(cm.update(model, path))
        validate_model(model, expect_content=False)
        self._finish_model(model)

    @gen.coroutine
    def _copy(self, copy_from, copy_to=None):
        """Copy a file, optionally specifying a target directory."""
        self.log.info(u"Copying {copy_from} to {copy_to}".format(
            copy_from=copy_from,
            copy_to=copy_to or '',
        ))
        if copy_from in [EXAMPLE_NB, MLSQL_NB]:
            # notebook_dir: /home/datalab/notebooks/{username}
            notebook_dir = self.contents_manager.info_string().split(": ")[1]
            src_file = "%s/%s" % (notebook_dir.rsplit("/", 1)[0], copy_from)
            copyfile(src_file, "%s/%s" % (notebook_dir, copy_from))
        model = yield maybe_future(self.contents_manager.copy(copy_from, copy_to))
        self.set_status(201)
        validate_model(model, expect_content=False)
        self._finish_model(model)

    @gen.coroutine
    def _upload(self, model, path):
        """Handle upload of a new file to path"""
        self.log.info(u"Uploading file to %s", path)
        model = yield maybe_future(self.contents_manager.new(model, path))
        self.set_status(201)
        validate_model(model, expect_content=False)
        self._finish_model(model)

    @gen.coroutine
    def _new_untitled(self, path, type='', ext=''):
        """Create a new, empty untitled entity"""
        self.log.info(u"Creating new %s in %s", type or 'file', path)
        model = yield maybe_future(self.contents_manager.new_untitled(path=path, type=type, ext=ext))
        self.set_status(201)
        validate_model(model, expect_content=False)
        self._finish_model(model)

    @gen.coroutine
    def _save(self, model, path):
        """Save an existing file."""
        chunk = model.get("chunk", None)
        if not chunk or chunk == -1:  # Avoid tedious log information
            self.log.info(u"Saving file at %s", path)
        model = yield maybe_future(self.contents_manager.save(model, path))
        validate_model(model, expect_content=False)
        self._finish_model(model)

    @web.authenticated
    @gen.coroutine
    def post(self, path=''):
        """Create a new file in the specified path.

        POST creates new files. The server always decides on the name.

        POST /api/contents/path
          New untitled, empty file or directory.
        POST /api/contents/path
          with body {"copy_from" : "/path/to/OtherNotebook.ipynb"}
          New copy of OtherNotebook in path
        """

        cm = self.contents_manager

        file_exists = yield maybe_future(cm.file_exists(path))
        if file_exists:
            raise web.HTTPError(400, "Cannot POST to files, use PUT instead.")

        dir_exists = yield maybe_future(cm.dir_exists(path))
        if not dir_exists:
            raise web.HTTPError(404, "No such directory: %s" % path)

        model = self.get_json_body()

        if model is not None:
            copy_from = model.get('copy_from')
            ext = model.get('ext', '')
            type = model.get('type', '')
            if copy_from:
                yield self._copy(copy_from, path)
            else:
                yield self._new_untitled(path, type=type, ext=ext)
        else:
            yield self._new_untitled(path)

    @web.authenticated
    @gen.coroutine
    def put(self, path=''):
        """Saves the file in the location specified by name and path.

        PUT is very similar to POST, but the requester specifies the name,
        whereas with POST, the server picks the name.

        PUT /api/contents/path/Name.ipynb
          Save notebook at ``path/Name.ipynb``. Notebook structure is specified
          in `content` key of JSON request body. If content is not specified,
          create a new empty notebook.
        """
        model = self.get_json_body()
        if model:
            if model.get('copy_from'):
                raise web.HTTPError(400, "Cannot copy with PUT, only POST")
            exists = yield maybe_future(self.contents_manager.file_exists(path))
            if exists:
                # notebook_dir: /home/datalab/notebooks/{username}
                notebook_dir = self.contents_manager.info_string().split(": ")[1]
                jupyter_username = notebook_dir.rsplit("/", 1)[1]
                # 如果jupyter_username是数字，代表是公共项目
                if jupyter_username.isdigit():
                    if not model.get('bk_username'):
                        self.finish(generate_response(False, RESPONSE_MESSAGE.get(BK_USERNAME_NULL_CODE),
                                                      BK_USERNAME_NULL_CODE, {}))
                    else:
                        status, code = check_project_auth(jupyter_username, model.get('bk_username'))
                        if status:
                            yield maybe_future(self._save(model, path))
                        else:
                            self.finish(generate_response(False, RESPONSE_MESSAGE.get(code), code, {}))
                else:
                    yield maybe_future(self._save(model, path))
            else:
                yield maybe_future(self._upload(model, path))
        else:
            yield maybe_future(self._new_untitled(path))

    @web.authenticated
    @gen.coroutine
    def delete(self, path=''):
        """delete a file in the given path"""
        cm = self.contents_manager
        self.log.warning('delete %s', path)
        yield maybe_future(cm.delete(path))

        head, file_name = os.path.split(path)
        notebook_dir = self.contents_manager.info_string().split(": ")[1]
        python_file = '%s/%s' % (notebook_dir, file_name.replace('ipynb', 'py'))
        errors = None
        try:
            if os.path.exists(python_file):
                # 删除py文件
                os.remove(python_file)

                # 删除git仓库中的py文件
                git_dir, user_name = notebook_dir.rsplit("/", 1)
                relative_python_file = '%s/%s' % (user_name, file_name.replace('ipynb', 'py'))
                repo = Repo(git_dir)
                index = repo.index
                index.remove(relative_python_file)
                index.commit('delete file: %s' % relative_python_file)
                # remote = repo.remote()
                # remote.push()

                # 删除文件相关的tag
                for tag in repo.tags:
                    tag_contents = tag.name.split(DELIMITER)
                    if relative_python_file == tag_contents[1]:
                        repo.delete_tag(tag)
                        # remote.push(refspec=(':%s' % tag))  # remove from remote
        except Exception as e:
            self.log.error("delete notebook error: %s", str(e))
            errors = str(e)
        finally:
            result, code, message = (True, SUCCESS_CODE, u'删除成功') if not errors else \
                (False, GIT_COMMAND_CODE, RESPONSE_MESSAGE.get(GIT_COMMAND_CODE))
            self.set_status(204)
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
            self.finish(generate_response(result, u"删除笔记：%s" % message, code, errors))


class CheckpointsHandler(APIHandler):

    @web.authenticated
    @gen.coroutine
    def get(self, path=''):
        """get lists checkpoints for a file"""
        cm = self.contents_manager
        checkpoints = yield maybe_future(cm.list_checkpoints(path))
        data = json.dumps(checkpoints, default=date_default)
        self.finish(data)

    @web.authenticated
    @gen.coroutine
    def post(self, path=''):
        """post creates a new checkpoint"""
        cm = self.contents_manager
        checkpoint = yield maybe_future(cm.create_checkpoint(path))
        data = json.dumps(checkpoint, default=date_default)
        location = url_path_join(self.base_url, 'api/contents',
            url_escape(path), 'checkpoints', url_escape(checkpoint['id']))
        self.set_header('Location', location)
        self.set_status(201)
        self.finish(data)


class ModifyCheckpointsHandler(APIHandler):

    @web.authenticated
    @gen.coroutine
    def post(self, path, checkpoint_id):
        """post restores a file from a checkpoint"""
        cm = self.contents_manager
        yield maybe_future(cm.restore_checkpoint(checkpoint_id, path))
        self.set_status(204)
        self.finish()

    @web.authenticated
    @gen.coroutine
    def delete(self, path, checkpoint_id):
        """delete clears a checkpoint for a given file"""
        cm = self.contents_manager
        yield maybe_future(cm.delete_checkpoint(checkpoint_id, path))
        self.set_status(204)
        self.finish()


class NotebooksRedirectHandler(IPythonHandler):
    """Redirect /api/notebooks to /api/contents"""
    SUPPORTED_METHODS = ('GET', 'PUT', 'PATCH', 'POST', 'DELETE')

    def get(self, path):
        self.log.warning("/api/notebooks is deprecated, use /api/contents")
        self.redirect(url_path_join(
            self.base_url,
            'api/contents',
            path
        ))

    put = patch = post = delete = get


class TrustNotebooksHandler(IPythonHandler):
    """ Handles trust/signing of notebooks """

    @web.authenticated
    @gen.coroutine
    def post(self,path=''):
        cm = self.contents_manager
        yield maybe_future(cm.trust_notebook(path))
        self.set_status(201)
        self.finish()


class NotebookVersionHandler(IPythonHandler):
    """ Notebook版本管理 """

    @web.authenticated
    @gen.coroutine
    def post(self, path=''):
        """ 版本提交"""
        body = self.get_json_body()
        version, commit_message, bk_username = body.get('version'), body.get('commit_message'), body.get('bk_username')
        code, errors = SUCCESS_CODE, None
        try:
            if version:
                if DELIMITER in version:
                    # tag以 变量DELIMITER 作为分隔符，所以不允许用户输入
                    code = SPECIAL_CHAR_CODE
                else:
                    head, file_name = os.path.split(path)
                    # notebook_dir: /home/datalab/notebooks/{username}
                    notebook_dir = self.contents_manager.info_string().split(": ")[1]
                    check_call(['jupytext', '--to', 'py', file_name], cwd=notebook_dir)

                    git_dir, user_name = notebook_dir.rsplit("/", 1)
                    # 创建版本库对象
                    repo = Repo(git_dir)
                    python_file = '%s/%s' % (user_name, file_name.replace('ipynb', 'py'))

                    for tag in sorted(repo.tags, key=lambda t: t.commit.committed_date, reverse=True):
                        tag_contents = tag.name.split(DELIMITER)
                        if python_file == tag_contents[1]:
                            if len(tag_contents) == 4 and DELETE_TAG in tag_contents[3]:
                                continue
                            tag_version = tag_contents[0]
                            if version == tag_version:
                                code = VERSION_EXIST_CODE
                                break
                    if code == SUCCESS_CODE:
                        # 获取版本库暂存区
                        index = repo.index
                        # 添加修改文件
                        index.add(python_file)
                        # 提交修改到本地仓库
                        commit_id = index.commit(commit_message)
                        tag = DELIMITER.join((version, python_file, bk_username))
                        repo.create_tag(path=tag, ref=commit_id)
                        # 获取远程仓库
                        # remote = repo.remote()
                        # 推送本地修改到远程仓库
                        # remote.push(tag)
                        # remote.push()
            else:
                code = VERSION_NULL_CODE
        except Exception as e:
            self.log.error("commit version error: %s", str(e))
            code, errors = GIT_COMMAND_CODE, str(e)
        finally:
            result = True if code == SUCCESS_CODE else False
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
            self.finish(generate_response(result, u"保存为新版本：%s" % RESPONSE_MESSAGE.get(code), code, errors))

    @web.authenticated
    @gen.coroutine
    def get(self, path=''):
        """ 获取历史版本信息 """
        head, file_name = os.path.split(path)
        # notebook_dir: /home/datalab/notebooks/{username}
        notebook_dir = self.contents_manager.info_string().split(': ')[1]
        git_dir, user_name = notebook_dir.rsplit('/', 1)
        data, errors = [], None
        try:
            # 创建版本库对象
            repo = Repo(git_dir)
            python_file = '%s/%s' % (user_name, file_name.replace('ipynb', 'py'))
            for tag in sorted(repo.tags, key=lambda t: t.commit.committed_date, reverse=True):
                tag_contents = tag.name.split(DELIMITER)
                if python_file == tag_contents[1]:
                    if len(tag_contents) == 4 and DELETE_TAG in tag_contents[3]:
                        continue
                    data.append({
                        'commit_id': tag.commit.hexsha,
                        'commit_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tag.commit.authored_date)),
                        'commit_message': tag.commit.message,
                        'version': tag_contents[0],
                        'author': tag_contents[2]
                    })
        except Exception as e:
            self.log.error("get version list error: %s", str(e))
            errors = str(e)
        finally:
            result, code = (True, SUCCESS_CODE) if not errors else (False, GIT_COMMAND_CODE)
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
            self.finish(generate_response(result, u"获取版本列表：%s" % RESPONSE_MESSAGE.get(code), code, errors, data))

    @web.authenticated
    @gen.coroutine
    def delete(self, path=''):
        """ 删除指定版本 """
        commit_id = self.get_query_argument('commit_id', default=None)
        # notebook_dir: /home/datalab/notebooks/{username}
        notebook_dir = self.contents_manager.info_string().split(": ")[1]
        git_dir, user_name = notebook_dir.rsplit("/", 1)
        errors = None
        try:
            # 创建版本库对象
            repo = Repo(git_dir)
            tag = u'%s' % repo.git.describe('--contains', commit_id)
            repo.delete_tag(tag)
            # remote = repo.remote()
            # remote.push(refspec=(':%s' % tag))  # remove from remote

            deleted_tag = DELIMITER.join((tag, '%s_%s' % (DELETE_TAG, str(time.time()))))
            repo.create_tag(path=deleted_tag, ref=commit_id)
            # remote.push(deleted_tag)
        except Exception as e:
            self.log.error("delete version error: %s", str(e))
            errors = str(e)
        finally:
            result, code = (True, SUCCESS_CODE) if not errors else (False, GIT_COMMAND_CODE)
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
            self.finish(generate_response(result, u"删除版本：%s" % RESPONSE_MESSAGE.get(code), code, errors))


class NotebookVersionDiffHandler(IPythonHandler):
    """ 获取版本间差异 """

    @web.authenticated
    @gen.coroutine
    def get(self, path=''):
        head, file_name = os.path.split(path)
        # notebook_dir: /home/datalab/notebooks/{username}
        notebook_dir = self.contents_manager.info_string().split(": ")[1]
        data, errors = {}, None
        try:
            # 需要将修改的内容保存为py文件以便进行差异对比
            check_call(['jupytext', '--to', 'py', file_name], cwd=notebook_dir)

            git_dir, user_name = notebook_dir.rsplit("/", 1)
            repo = Repo(git_dir)
            python_file = '%s/%s' % (user_name, file_name.replace('ipynb', 'py'))
            repo.index.add(python_file)
            git = repo.git
            commit_id = self.get_query_argument('commit_id', default=None)
            if commit_id:
                file_content = git.show(':{}'.format(python_file))
                diff_file_content = git.show('{}:{}'.format(commit_id, python_file))
                data = {'file_content': file_content, 'diff_file_content': diff_file_content}
        except Exception as e:
            self.log.error("get version diff error: %s", str(e))
            errors = str(e)
        finally:
            result, code = (True, SUCCESS_CODE) if not errors else (False, GIT_COMMAND_CODE)
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
            self.finish(generate_response(result, u"获取版本间差异：%s" % RESPONSE_MESSAGE.get(code), code, errors, data))


class NotebookVersionResetHandler(IPythonHandler):
    """ 版本回退 """

    @web.authenticated
    @gen.coroutine
    def put(self, path=''):
        body = self.get_json_body()
        reset_commit_id, bk_username = body.get('commit_id'), body.get('bk_username')
        head, file_name = os.path.split(path)
        # notebook_dir: /home/datalab/notebooks/{username}
        notebook_dir = self.contents_manager.info_string().split(": ")[1]
        git_dir, user_name = notebook_dir.rsplit("/", 1)
        py_file_name = file_name.replace('ipynb', 'py')
        py_file_path = '%s/%s' % (user_name, py_file_name)
        errors = None
        try:
            # 创建快照
            repo = Repo(git_dir)
            index = repo.index
            index.add(py_file_path)
            commit_id = index.commit('')
            tag = DELIMITER.join(
                ('snapshot_%s' % time.strftime("%Y.%m.%d-%H.%M.%S", time.localtime()), py_file_path, bk_username)
            )
            repo.create_tag(path=tag, ref=commit_id)
            # remote = repo.remote()
            # remote.push(tag)
            # remote.push()

            git = repo.git
            git.checkout(reset_commit_id, py_file_path)
            check_call(['jupytext', '--to', 'ipynb', py_file_name], cwd=notebook_dir)
        except Exception as e:
            self.log.error("version reset error: %s", str(e))
            errors = str(e)
        finally:
            result, code = (True, SUCCESS_CODE) if not errors else (False, GIT_COMMAND_CODE)
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
            self.finish(generate_response(result, u"版本回退：%s" % RESPONSE_MESSAGE.get(code), code, errors))

#-----------------------------------------------------------------------------
# URL to handler mappings
#-----------------------------------------------------------------------------


_checkpoint_id_regex = r"(?P<checkpoint_id>[\w-]+)"
ipynb_path_regex = r"(?P<path>\w*.ipynb)"

default_handlers = [
    (r"/api/contents%s/checkpoints" % path_regex, CheckpointsHandler),
    (r"/api/contents%s/checkpoints/%s" % (path_regex, _checkpoint_id_regex),
        ModifyCheckpointsHandler),
    (r"/api/contents%s/trust" % path_regex, TrustNotebooksHandler),
    (r"/api/contents", ContentsHandler),
    (r"/api/contents/%s" % ipynb_path_regex, ContentsHandler),
    (r"/api/contents/%s/version" % ipynb_path_regex, NotebookVersionHandler),
    (r"/api/contents/%s/version/diff" % ipynb_path_regex, NotebookVersionDiffHandler),
    (r"/api/contents/%s/version/reset" % ipynb_path_regex, NotebookVersionResetHandler),
    (r"/api/notebooks/?(.*)", NotebooksRedirectHandler)
]
