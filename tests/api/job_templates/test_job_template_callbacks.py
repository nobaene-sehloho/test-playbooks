from urlparse import urlparse
import httplib
import socket
import json

from towerkit.config import config
from towerkit import utils
import pytest

from tests.api import Base_Api_Test


@pytest.mark.api
@pytest.mark.ha_tower
@pytest.mark.skip_selenium
@pytest.mark.destructive
class TestJobTemplateCallbacks(Base_Api_Test):

    pytestmark = pytest.mark.usefixtures('authtoken', 'install_enterprise_license')

    def test_assignment_of_host_config_key(self, job_template, host_config_key):
        """Confirm that when a job template's host config key is set, it is exposed through JT and callback endpoint"""
        job_template.host_config_key = host_config_key
        assert job_template.host_config_key == host_config_key

        callback = job_template.get_related('callback')
        assert callback.host_config_key == host_config_key

    def test_matching_hosts_empty_in_nonmember_query(self, factories, host_config_key):
        """Assert a GET on the callback resource returns an empty list of matching hosts when made by a nonmember"""
        host = factories.host(variables=json.dumps(dict(ansible_ssh_host='169.254.1.0')))
        job_template = factories.job_template(inventory=host.ds.inventory)

        job_template.host_config_key = host_config_key
        callback = job_template.get_related('callback')
        assert len(callback.matching_hosts) == 0

    @pytest.fixture(scope='class')
    def callback_host(self, ansible_module_cls):
        base_url = urlparse(config.base_url)
        port = '' if base_url.port is None else ':{0.port}'.format(base_url)
        scheme = 'http' if base_url.scheme is None else base_url.scheme

        is_docker = False
        manager = ansible_module_cls.inventory_manager
        tower_hosts = manager.get_group_dict().get('tower')
        if tower_hosts:
            is_docker = manager.get_host(tower_hosts[0]).get_vars().get('ansible_connection') == 'docker'

        host = 'localhost' if is_docker else base_url.hostname
        return '{0}://{1}{2}'.format(scheme, host, port)

    def test_matching_hosts_contains_member_in_member_query(self, ansible_runner, host_config_key, job_template,
                                                            host_with_default_ipv4_in_variables, callback_host):
        """Assert a GET on the callback resource returns a list containimg a matching host if made by that host"""
        job_template.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="GET",
                                       status_code=httplib.OK,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template),
                                       user=config.credentials.users.admin.username,
                                       password=config.credentials.users.admin.password,
                                       force_basic_auth=True,
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.OK
        assert not result['changed']
        assert 'failed' not in result

        matching_hosts = contacted.values()[0]['json']['matching_hosts']
        assert len(matching_hosts) == 1
        # account for dev container
        desired_hostname = 'local' if 'localhost' in callback_host else host_with_default_ipv4_in_variables.name
        assert matching_hosts[0] == desired_hostname

    def test_provision_failure_with_empty_inventory(self, ansible_runner, factories, host_config_key, callback_host):
        """Verify launch failure when called on a job template with an empty inventory"""
        job_template = factories.job_template()
        job_template.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.BAD_REQUEST
        assert result['failed']
        assert result['json']['msg'] == 'No matching host could be found!'

    @pytest.fixture(scope="function")
    def hosts_with_actual_ipv4_for_name_and_random_ssh_host(self, request, factories, group, callback_host):
        """Create an inventory host matching the public ipv4 address of the system running pytest."""
        if 'localhost' in callback_host:  # account for dev container
            local_ipv4_addresses = ['127.0.0.1', 'localhost']
        else:
            local_ipv4_addresses = socket.gethostbyname_ex(socket.gethostname())[2]

        hosts = []
        for ipv4_addr in local_ipv4_addresses:
            host = factories.host(name=ipv4_addr, inventory=group.ds.inventory,
                                  variables=json.dumps(dict(ansible_ssh_host=utils.random_ipv4(),
                                                             ansible_connection="local")))
            group.add_host(host)
            hosts.append(host)

        return hosts

    def test_provision_failure_with_non_matching_ssh_host(self, ansible_runner, factories, host_config_key,
                                                          hosts_with_actual_ipv4_for_name_and_random_ssh_host,
                                                          callback_host):
        """Verify launch failure when a matching host.name is found, but ansible_ssh_host is different."""
        inventory = hosts_with_actual_ipv4_for_name_and_random_ssh_host[0].ds.inventory
        job_template = factories.job_template(inventory=inventory)
        job_template.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert 'status' in result
        assert result['status'] == httplib.BAD_REQUEST
        assert result['failed']
        assert result['json']['msg'] == 'No matching host could be found!'

    def test_provision_failure_with_multiple_host_matches(self, ansible_runner, factories, ansible_default_ipv4,
                                                          host_config_key, callback_host):
        """Verify launch failure when launching a job_template where multiple hosts match"""
        inventory = factories.inventory()

        # account for dev container
        ansible_ssh_host = '127.0.0.1' if 'localhost' in callback_host else ansible_default_ipv4
        for name in ('matching_host', 'another_matching_host'):
            factories.host(name=name, inventory=inventory,
                           variables=json.dumps(dict(ansible_ssh_host=ansible_ssh_host,
                                                     ansible_connection="local")))

        job_template = factories.job_template(inventory=inventory)
        job_template.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.BAD_REQUEST
        assert 'failed' in result and result['failed']
        assert result['json']['msg'] == 'Multiple hosts matched the request!'

    def test_provision_failure_with_incorrect_hostkey(self, ansible_runner, job_template,
                                                      host_with_default_ipv4_in_variables, host_config_key,
                                                      callback_host):
        """Verify launch failure when providing incorrect host_config_key"""
        job_template.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template),
                                       body_format='json',
                                       body=dict(host_config_key='BOGUS'),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.FORBIDDEN
        assert result['failed']
        assert result['json']['detail'] == 'You do not have permission to perform this action.'

    def test_provision_failure_without_credential(self, ansible_runner, job_template_no_credential,
                                                  host_with_default_ipv4_in_variables, host_config_key, callback_host):
        """Verify launch failure when launching a job_template with no credentials"""
        job_template_no_credential.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template_no_credential),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.BAD_REQUEST
        assert result['failed']
        assert result['json']['msg'] == 'Cannot start automatically, user input required!'

    def test_provision_failure_with_ask_credential(self, ansible_runner, job_template_ask,
                                                   host_with_default_ipv4_in_variables, host_config_key, callback_host):
        """Verify launch failure when launching a job_template with ASK credentials"""
        job_template_ask.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template_ask),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.BAD_REQUEST
        assert result['failed']
        assert result['json']['msg'] == 'Cannot start automatically, user input required!'

    def test_provision_failure_with_unprovided_survey_variables_needed_to_start(self, ansible_runner,
                                                                                job_template_variables_needed_to_start,
                                                                                host_with_default_ipv4_in_variables,
                                                                                host_config_key, callback_host):
        """Verify launch failure when launching a job_template that has required survey variables."""
        job_template_variables_needed_to_start.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host,
                                                                            job_template_variables_needed_to_start),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.BAD_REQUEST
        assert result['failed']
        assert result['json']['msg'] == 'Cannot start automatically, user input required!'

    def test_provision_with_provided_variables_needed_to_start(self, ansible_runner,
                                                               job_template_variables_needed_to_start,
                                                               host_with_default_ipv4_in_variables, host_config_key,
                                                               callback_host):
        """Verify launch success when launching a job_template while providing required survey variables."""
        job_template_variables_needed_to_start.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host,
                                                                            job_template_variables_needed_to_start),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key,
                                                 extra_vars=dict(likes_chicken='yes',
                                                                 favorite_color='red')),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.CREATED
        assert not result['changed']
        assert 'failed' not in result

        job_id = result['location'].split('jobs/')[1].split('/')[0]
        job = job_template_variables_needed_to_start.related.jobs.get(id=job_id).results.pop().wait_until_completed()
        assert job.launch_type == "callback"
        assert job.is_successful

    def test_provision_job_template_with_limit(self, api_jobs_url, ansible_runner, job_template_with_random_limit,
                                               host_with_default_ipv4_in_variables, host_config_key, callback_host):
        """Assert that launching a callback job against a job_template with an
        existing 'limit' parameter successfully launches and that it is launched
        with a value for "limit" that matches our test host.
        """
        job_template_with_random_limit.host_config_key = host_config_key

        contacted = ansible_runner.uri(method="POST",
                                       timeout=60,
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host,
                                                                            job_template_with_random_limit),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.CREATED
        assert not result['changed']
        assert 'failed' not in result

        job_id = result['location'].split('jobs/')[1].split('/')[0]
        job = job_template_with_random_limit.related.jobs.get(id=job_id).results.pop().wait_until_completed()
        assert job.launch_type == "callback"
        assert job.is_successful

        # account for dev container
        desired_hostname = 'local' if 'localhost' in callback_host else host_with_default_ipv4_in_variables.name
        assert job.limit == desired_hostname

    @pytest.mark.parametrize(
        'ask_on_launch,provided_extra_vars,expected_extra_vars',
        [[False, {}, {}],
         [False, dict(dont_filter_me=True, ansible_filter_me=1234), {}],
         [True, dict(dont_filter_me=True, ansible_filter_me=1234), dict(dont_filter_me=True)],
         [False, "{\"dont_filter_me\": true, \"ansible_filter_me\": 1234}", {}],
         [True, "{\"dont_filter_me\": true, \"ansible_filter_me\": 1234}", dict(dont_filter_me=True)],
         [False, '---\ndont_filter_me: true\nansible_filter_me: 1234', {}],
         [True, '---\ndont_filter_me: true\nansible_filter_me: 1234', dict(dont_filter_me=True)]]
    )
    def test_provision_with_provided_extra_vars(self, ansible_runner, job_template, host_with_default_ipv4_in_variables,
                                                host_config_key, ask_on_launch, provided_extra_vars,
                                                expected_extra_vars, callback_host):
        """Confirms that provided extra_vars in callback request are properly accepted and filtered/ignored"""
        job_template.host_config_key = host_config_key
        job_template.ask_variables_on_launch = ask_on_launch

        contacted = ansible_runner.uri(method="POST", timeout=90, status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template),
                                       body_format='json', validate_certs=False,
                                       body=dict(host_config_key=host_config_key, extra_vars=provided_extra_vars))

        result = contacted.values().pop()
        assert result['status'] == httplib.CREATED
        assert not result['changed']
        assert 'failed' not in result

        job_id = result['location'].split('jobs/')[1].split('/')[0]
        job = job_template.related.jobs.get(id=job_id).results.pop().wait_until_completed()
        assert job.launch_type == "callback"
        assert job.is_successful

        host_summaries = job.related.job_host_summaries.get()
        assert host_summaries.count == 1

        # account for dev container
        desired_id = host_with_default_ipv4_in_variables.id
        if 'localhost' in callback_host:
            inventory = host_with_default_ipv4_in_variables.ds.inventory
            desired_id = inventory.related.hosts.get(name='local').results.pop().id
        assert host_summaries.results[0].host == desired_id
        assert json.loads(job.extra_vars) == expected_extra_vars

    def test_provision_without_required_extra_vars(self, ansible_runner, job_template,
                                                   host_with_default_ipv4_in_variables,
                                                   host_config_key, callback_host):
        """Confirms that launch attempts for `ask_variables_on_launch` jobs fail without extra_vars"""
        job_template.host_config_key = host_config_key
        job_template.ask_variables_on_launch = True

        contacted = ansible_runner.uri(method="POST", timeout=90, status_code=httplib.CREATED,
                                       url='{0}/{1.related.callback}'.format(callback_host, job_template),
                                       body_format='json', validate_certs=False,
                                       body=dict(host_config_key=host_config_key))

        callback_result = contacted.values().pop()
        assert callback_result['status'] == httplib.BAD_REQUEST
        assert callback_result['failed']
        assert callback_result['json']['msg'] == 'Cannot start automatically, user input required!'

    def test_provision_failure_with_currently_running_and_simultaneous_disallowed(
            self, api_jobs_url, ansible_runner, job_template,
            host_with_default_ipv4_in_variables, host_config_key,
            callback_host
        ):
        """Verify that issuing a callback, while a callback job from the same host is already running, fails."""
        job_template.patch(host_config_key=host_config_key,
                           playbook='sleep.yml',
                           extra_vars='{"sleep_interval": 10}')

        for attempt in range(3):
            contacted = ansible_runner.uri(method="POST",
                                           timeout=60,
                                           status_code=httplib.CREATED,
                                           url='{0}{1.related.callback}'.format(callback_host, job_template),
                                           body_format='json',
                                           body=dict(host_config_key=host_config_key),
                                           validate_certs=False)

            result = contacted.values().pop()
            if attempt == 0:
                assert result['status'] == httplib.CREATED
                assert not result['changed']
                assert 'failed' not in result
                job_id = result['location'].split('jobs/')[1].split('/')[0]
            else:
                assert result['status'] == httplib.BAD_REQUEST
                assert 'failed' in result

        job = job_template.related.jobs.get(id=job_id).results.pop().wait_until_completed()
        assert job.launch_type == "callback"
        assert job.is_successful

        host_summaries = job.get_related('job_host_summaries')
        assert host_summaries.count == 1

        # account for dev container
        desired_id = host_with_default_ipv4_in_variables.id
        if 'localhost' in callback_host:
            inventory = host_with_default_ipv4_in_variables.ds.inventory
            desired_id = inventory.related.hosts.get(name='local').results.pop().id
        assert host_summaries.results[0].host == desired_id

    def test_provision_with_inventory_update_on_launch(self, api_jobs_url, ansible_runner, host_config_key,
                                                       custom_group, job_template, ansible_default_ipv4,
                                                       tower_version_cmp, callback_host):
        """Assert that a callback job against a job_template also initiates an inventory_update (when configured)."""
        job_template.host_config_key = host_config_key

        custom_group.related.inventory_source.patch(update_on_launch=True)

        assert custom_group.get_related('inventory_source').last_updated is None

        contacted = ansible_runner.uri(method="POST",
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert 'failed' not in result
        assert result['status'] == httplib.CREATED
        assert not result['changed']
        job_id = result['location'].split('jobs/')[1].split('/')[0]
        job = job_template.related.jobs.get(id=job_id).results.pop().wait_until_completed()
        assert job.is_successful

        inv_source_pg = custom_group.get_related('inventory_source')
        assert inv_source_pg.is_successful

        inv_update_pg = inv_source_pg.get_related('last_update')
        assert inv_update_pg.is_successful

    def test_provision_without_inventory_update_on_launch(self, ansible_runner, factories, host_config_key,
                                                          custom_group, ansible_default_ipv4, callback_host):
        """Assert that a callback job against a job_template does not initiate an inventory_update"""
        inventory = custom_group.ds.inventory
        ansible_ssh_host = '127.0.0.1' if 'localhost' in callback_host else ansible_default_ipv4
        factories.host(inventory=inventory,
                       variables=json.dumps(dict(ansible_ssh_host=ansible_ssh_host,
                                                 ansible_connection="local")))

        job_template = factories.job_template(inventory=inventory)
        job_template.host_config_key = host_config_key

        custom_group.related.inventory_source.patch(update_on_launch=False)

        assert custom_group.get_related('inventory_source').last_updated is None

        contacted = ansible_runner.uri(method="POST",
                                       timeout=60,
                                       status_code=httplib.CREATED,
                                       url='{0}{1.related.callback}'.format(callback_host, job_template),
                                       body_format='json',
                                       body=dict(host_config_key=host_config_key),
                                       validate_certs=False)

        result = contacted.values().pop()
        assert result['status'] == httplib.CREATED
        assert 'failed' not in result
        assert not result['changed']
        job_id = result['location'].split('jobs/')[1].split('/')[0]
        job_template.related.jobs.get(id=job_id).results.pop().wait_until_completed()

        assert custom_group.get_related('hosts').count == 0
        assert custom_group.get_related('children').count == 0
        assert custom_group.get_related('inventory_source').last_updated is None
