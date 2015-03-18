import json
import common.utils
from common.api.pages import Base, Base_List, json_setter, json_getter


class Unified_Job_Template_Page(Base):
    '''
    Base class for unified job template pages (e.g. project, inventory_source,
    and job_template).
    '''

    base_url = '/api/v1/unified_job_templates/{id}/'

    name = property(json_getter('name'), json_setter('name'))
    description = property(json_getter('description'), json_setter('description'))
    status = property(json_getter('status'), json_setter('status'))
    last_updated = property(json_getter('last_updated'), json_setter('last_updated'))
    last_update_failed = property(json_getter('last_update_failed'), json_setter('last_update_failed'))
    last_job_run = property(json_getter('last_job_run'), json_setter('last_job_run'))
    last_job_failed = property(json_getter('last_job_failed'), json_setter('last_job_failed'))
    has_schedules = property(json_getter('has_schedules'), json_setter('has_schedules'))

    def __str__(self):
        output = "<%s " % self.__class__.__name__
        for attr in ('id', 'name', 'status', 'source', 'last_update_failed',
                     'last_updated', 'result_traceback', 'job_explanation', 'job_args'):
            if hasattr(self, attr):
                output += "%s:%s" % (attr, getattr(self, attr))
        # NOTE: I use .replace('%', '%%') to workaround an odd string
        # formatting issue where result_stdout contained '%s'.  This later caused
        # a python traceback when attempting to display output from this method.
        return output.replace('%', '%%')

    def get_related(self, name, **kwargs):
        assert name in self.json['related'], \
            "Unsupported related attribute '%s'" % name

        if name == 'start':
            related = Base(self.testsetup, base_url=self.json['related'][name])
        elif name == 'schedules':
            from schedules import Schedules_Page
            related = Schedules_Page(self.testsetup, base_url=self.json['related'][name])
        else:
            raise NotImplementedError
        return related.get(**kwargs)

    def wait_until_started(self, interval=1, verbose=0, timeout=60):
        '''Wait until a unified_job_template has started.'''
        return common.utils.wait_until(
            self, 'status',
            ('new', 'pending', 'waiting', 'running',),
            interval=interval, verbose=verbose, timeout=timeout)

    def wait_until_completed(self, interval=5, verbose=0, timeout=60 * 8):
        '''Wait until a unified_job_template has completed.'''
        return common.utils.wait_until(
            self, 'status',
            ('successful', 'failed', 'error', 'canceled',),
            interval=interval, verbose=verbose, timeout=timeout)

    def launch(self, **kwargs):
        '''
        Launch the unified_job_template using related->launch endpoint.  Note,
        not all unified_job_templates support launch.  An exception will be
        raised when attempting to launch a unified_job_template that does not
        support launch.
        '''
        # get related->launch
        launch_pg = self.get_related('launch')

        # assert can_start_without_user_input
        assert launch_pg.can_start_without_user_input, \
            "The specified unified_job_template (id:%s) is not able to launch without user input.\n%s" % \
            (launch_pg.id, json.dumps(launch_pg.json, indent=2))

        # launch the job_template
        result = launch_pg.post(**kwargs)

        # return job
        jobs_pg = self.get_related('jobs', id=result.json['job'])
        assert jobs_pg.count == 1, \
            "job_template launched (id:%s) but job not found in response at %s/jobs/" % \
            (result.json['job'], self.url)
        return jobs_pg.results[0]

    @property
    def is_successful(self):
        '''An unified_job_template is considered successful when:
            1) status == 'successful'
            2) not last_update_failed
            3) last_updated
        '''
        return self.status == 'successful' and \
            not self.last_update_failed and \
            self.last_updated is not None


class Unified_Job_Templates_Page(Unified_Job_Template_Page, Base_List):
    base_url = '/api/v1/unified_job_templates/'
