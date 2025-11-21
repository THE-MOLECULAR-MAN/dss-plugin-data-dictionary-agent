"""docstring TBD"""

# This file is the actual code for the Python runnable auto-documentation-generation

import json
import sys

# from json import dumps
import traceback

from datadictionaryagent.utils import *

# import pandas as pd
import dataiku
from dataiku.runnables import Runnable, ResultTable
from dataikuapi.utils import DataikuException
import dataikuapi


class MyRunnable(Runnable):
    """Base class for Dataiku DSS Macro in a plugin"""

    def __init__(self, project_key, config, plugin_config):
        """
        :param project_key: the project in which the runnable executes
        :param config: the dict of the configuration of the object
        :param plugin_config: contains the plugin settings
        """
        print('MyRunnable Constructor start')
        self.project_key = project_key
        self.config = config
        self.plugin_config = plugin_config

        self.__num_ai_services_used = 0
        self.__progress = 0
        self.__inscope  = 1
        self.__language                = self.config["language"]
        self.__project_purpose         = self.config["project_purpose"]

        self.__project_length          = self.config["project_length"]
        self.__flowzone_purpose        = self.config["flowzone_purpose"]
        self.__flowzone_length         = self.config["flowzone_length"]
        self.__save_description        = self.config["save_description"]
        #self.__tagname_aigen           = self.config["tagname_aigen"]
        #self.__tagname_do_not_autofill = self.config["tagname_DoNotAutoFill"]
        #arr = self.config["object_types_to_autofill"]
        #print(f"list of obj to autofill {str(arr)}")

        self.__autofill_projects  = "projects"  in self.config["object_types_to_autofill"]
        self.__autofill_flowzones = "flowzones" in self.config["object_types_to_autofill"]
        self.__autofill_datasets  = "datasets"  in self.config["object_types_to_autofill"]

        self.__client = dataiku.api_client()
        
        # multi-select
        pf = self.config["project_filter"]

        if pf == "this_project_only":
            self.__projects_list = [self.project_key]
            self.__inscope  = 1
        elif pf == "all_projects":
            self.__projects_list = self.__client.list_project_keys()
            self.__inscope  = len(self.__projects_list)
        else:
            print(f"[WARNING] invalid project_filter: {pf} Defaulting to this project only")
            self.__projects_list = [self.project_key]
              
        # print(self)

    @property
    def num_ai_services_used(self):
        """Returns the total number of AI services used during the auto documentation process.

        Returns:
            int: The count of AI services that were utilized
        """
        return self.__num_ai_services_used

    def get_progress_target(self):
        """
        If the runnable will return some progress info, have this function return a tuple of
        (target, unit) where unit is one of: SIZE, FILES, RECORDS, NONE
        """
        # this function runs once and only once, and unfortunately it cannot dynamically update the target as the scope grows.
#         return (self.__inscope, 'RECORDS')
        return (1, None)
        # return None # this disables the status updates
    
    def run_datasets(self, progress_callback):
        """
        x
        """
        
        if not self.__autofill_datasets:
            print("Skipping Datasets since they're not selected")
            return None

        # iterate through projects
        for project_key in self.__projects_list:
            project_handle = self.__client.get_project(project_key)

            # iterate through all datasets in that project
            self.__inscope += len(project_handle.list_datasets())
            for dataset in project_handle.list_datasets():
                try:
                    rt_record = []
                    status = 'start'
                    rt_record.append('dataset')

                    dataset_id = dataset["name"]
                    rt_record.append(project_key + ' - ' + dataset_id)                    
                    dataset_handle = project_handle.get_dataset(dataset_id)

                    if not dataset_handle.exists():
                        status = 'skipped - dataset does not exist'
                        continue

                    # check if there is no schema
                    if len(dataset["schema"].get("columns", "")) == 0:
                        status = 'skipped - empty schema'
                        continue

                    # skip this dataset if it already has all of the description fields filled out
                    #if not dataset_has_full_documentation(project_handle, dataset_id):

                    # skip this dataset if it has ANY of the description fields filled out
                    if not dataset_has_any_documentation(project_handle, dataset_id):
                        # test if the first row can be read. VERY IMPORTANT to filter out a lot of
                        # wasted AI Services calls.
                        if not read_first_dataset_row(project_key, dataset_id):
                            status = 'skipped - dataset could not be read'
                            continue

                        print(
                            f"Auto-generating documentation for {project_key}'s dataset: {dataset_id} ..."
                        )
                        try:
                            # always increment this BEFORE calling generate_ai_description since
                            # generate_ai_description often raises an exception
                            self.__num_ai_services_used += 1

                            # this blocks execution, doesn't utilize Futures/JobID system
                            # actually generate and save the description
                            _ = dataset_handle.generate_ai_description(
                                language=self.__language,
                                save_description=self.__save_description,
                            )
                            if self.__save_description:
                                status = 'Generated & updated'
                            else:
                                status = 'Generated but dry run, not updated'

                        #                 if SAVE_DESCRIPTION and dataset_has_full_documentation(project_handle, dataset_id):
                        #                     print(f"Successfully filled out all fields for {dataset_id}")
                        #                 else:
                        #                     print(f"Attempted to fill in description for dataset, but failed to take effect: {dataset_id}")
                        #                     print(x)
                        

                        except DataikuException as e:
                            # there are so many different types of exceptions that occur
                            # java.lang.IllegalArgumentException: Column not found in schema:
                            print(
                                f"[ERROR] Exception {e} when autofilling: {project_key} - {dataset_id}"
                            )
                            status = 'error - DataikuException'
                            continue
                    else:
                        status = 'skipped - dataset already had some description'
                finally:
                    self.__progress += 1
                    progress_callback(self.__progress)
                    rt_record.append(status)
                    self.__rt.add_record(rt_record)


    def run_flowzones(self, progress_callback):
        """
        Iterates through projects and their flow zones to generate AI descriptions where needed.

        This method processes each project in the projects list, examining their flow zones.
        For each flow zone that meets the criteria (non-empty and lacking a description),
        it triggers AI-powered description generation.

        Parameters:
            None

        Returns:
            None

        Side Effects:
            - Updates flow zone descriptions in Dataiku projects
            - Increments self.__num_ai_services_used counter
            - Prints status messages to console

        Raises:
            DataikuException: If there's an error accessing project data or generating descriptions
            json.JSONDecodeError: If there's an error parsing flow zone settings
        """
        if not self.__autofill_flowzones:
            print("Skipping Flowzones since they're not selected")
            return None
        
        # Iterate through the list of projects
        for project_key in self.__projects_list:
            project_handle = self.__client.get_project(project_key)
            flow_handle = project_handle.get_flow()

            # Iterate through each flow zone in a specific project
            self.__inscope += len(flow_handle.list_zones())
            for flow_zone_handle in flow_handle.list_zones():
                try:
                    rt_record = []
                    status = 'start'     
                    rt_record.append('flow zone')
                    rt_record.append(project_key + ' - ' + flow_zone_handle.name)
                    
                    # Ensure that the flow zone meets the requirements for
                    # AI-Gen descriptions before attempting to have AI
                    # generate the description.
                    if is_flowzone_empty(flow_zone_handle):
                        # note: cannot call the flow zone name, it will throw an exception if you try to get it.
                        status = 'skipped - empty flow zone'
                        continue

                    # get the settings and name of the flow zone
                    flow_zone_settings = flow_zone_handle.get_settings().get_raw() # may throw exception?
                    flow_zone_name = flow_zone_settings.get("name", "") # may throw exception?
                          
                    # only have AI write the description if there is not one there already
                    if not flow_zone_has_description(flow_zone_handle):
                        print(
                            f"[CREATE] Generating flow zone documentation for {project_key}"
                        )
                        # bug is below here:
                        self.__num_ai_services_used += 1
                        flow_zone_handle.generate_ai_description(
                            language=self.__language,
                            purpose=self.__flowzone_purpose,
                            length=self.__flowzone_length,
                            save_description=self.__save_description,
                        )
                        if self.__save_description:
                            status = 'Generated & updated'
                        else:
                            status = 'Generated but dry run, not updated'
                    else:
                        status = 'skipped - already has description'
                except (DataikuException, json.JSONDecodeError) as e:
                    status = 'Error - DataikuException or JSONDecodeError'
                    pretty_print_dict(flow_zone_settings)
                    continue
                finally:
                    self.__progress += 1
                    progress_callback(self.__progress)
                    rt_record.append(status)
                    self.__rt.add_record(rt_record)


    def run_projects(self, progress_callback):
        """
        x
        """
        if not self.__autofill_projects:
            print("Skipping Projects since they're not selected")
            return None

        # iterate through the list of projects
        self.__inscope += len(self.__projects_list)        
        for project_key in self.__projects_list:
            try:
                rt_record = []
                status = 'start'
                rt_record.append('project')
                rt_record.append(project_key)                
                project_handle = self.__client.get_project(project_key)

                # Ensure that the project meets the requirements for creating
                # AI generated descriptions
                if is_project_empty(project_handle):
                    print(
                        f"[SKIP] Project must have datasets or recipes in flow, can't create description: {project_key}"
                    )
                    status = 'Skipped - empty project'
                    continue

                # Only generate descriptions if there is not one already:
                if is_project_description_empty(project_handle):
                    print(
                        f"Project {project_key} has an empty description, generating AI description for it."
                    )
                    self.__num_ai_services_used += 1

                    # https://developer.dataiku.com/latest/api-reference/python/projects.html#dataikuapi.dss.project.DSSProject.generate_ai_description
                    project_handle.generate_ai_description(
                        language=self.__language,
                        purpose=self.__project_purpose,
                        length=self.__project_length,
                        save_description=self.__save_description,
                    )
                    if self.__save_description:
                        status = 'Generated & updated'
                    else:
                        status = 'Generated but dry run, not updated'
                else:
                    status = 'Skipped - already had non-empty description'

            except json.JSONDecodeError:
                print(
                    f"[JSONDecodeError] Creating project description for {project_key}"
                )
                status = 'Exception - JSONDecodeError'
                continue
            finally:
                self.__progress += 1
                progress_callback(self.__progress)
                rt_record.append(status)
                self.__rt.add_record(rt_record)

                
    def run(self, progress_callback):
        """
        The progress_callback is a function expecting 1 value: current progress
        """
        self.__rt = ResultTable()
        self.__rt.add_column("1", "Object Type", "STRING")
        self.__rt.add_column("2", "Object Name", "STRING")
        self.__rt.add_column("2", "Autofill status", "STRING")        
        
        self.run_datasets(progress_callback)
        self.run_flowzones(progress_callback)
        self.run_projects(progress_callback)
        return self.__rt
        