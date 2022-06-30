import streamlit as st
import os.path, io, sys, getopt
from google.oauth2 import service_account
from googleapiclient.discovery import build

AC_CRED = st.secrets["ps_service_account"]
SCOPES = ['https://www.googleapis.com/auth/drive']

# If modifying these scopes, delete the file token.json.
src_root_id = '1o6WEU0XkBtki8wiks8nAoGNW7ZEsAcHP'
trg_root_id = '14UTkwUFQFx3Wh-P_eOQNDufxjoR2jQzV'
src_folders = ['system_YYYYMM']
v_sys_name = 'system'
v_month = 'YYYYMM'

################ python class ##################
# functions to perform the google drive operations - create folder, copy files/folders etc.
class gdrive:

    def get_gdrive_service(self):
        #function to authenticate and return the google drive service

        creds = service_account.Credentials.from_service_account_info(AC_CRED)
        scope_creds = creds.with_scopes(SCOPES)

        return build('drive', 'v3', credentials=scope_creds)

    def get_file_dict(self, service, parentid=None):
        """returns the list of file name and ids for a drive, includes subfolders
        Args:
            service: Drive API service instance.
            parentid: parent folder ID where the source folder is copied
        Returns:
            File or Folder ID
        """
        file_dict = {}
        # list of files and folders in source folder
        results = service.files().list(
            pageSize=10, fields="nextPageToken, files(id, name, mimeType)",
            q="'" + parentid + "' in parents and trashed=false").execute()
        files = results.get('files', [])

        # recursively looping thru folders/subfolders and files
        for file in files:
            if file['mimeType'] == 'application/vnd.google-apps.folder':
                ### Use recursion to search sub-folder
                file_dict[file['name']] = file['id']
                new_dict = self.get_file_dict(service, parentid=file['id'])
                #file_dict = file_dict | new_dict
                file_dict = dict(file_dict.items() | new_dict.items())
            else:
                file_dict[file['name']] = file['id']

        return file_dict

    def get_folder_id(self, service, folder_name, parentid=None):
        """returns the list of folder id/name (only) and ids for a drive
        Args:
            service: Drive API service instance.
            parentid: parent folder ID where the source folder is copied
        Returns:
            List of Folder Id and Folder name
        """
        folder_id = None

        # list of files and folders in source folder
        results = service.files().list(
            pageSize=10, fields="nextPageToken, files(id, name)",
            q="'" + parentid + "' in parents and trashed=false and mimeType = 'application/vnd.google-apps.folder'").execute()
        folders = results.get('files', [])

        for folder in folders:
            #print(folder['name'], folder['id'])
            if folder['name'] == folder_name:
                folder_id = folder['id']
                break

        return folder_id

    def copy_file(self, service, origin_file_id, copy_title, parentid=None):
        """Copy an existing file.
        Args:
            service: Drive API service instance.
            origin_file_id: ID of the origin file to copy.
            copy_title: Title of the copy.
        Returns:
            The copied file if successful, None otherwise.
        """
        copied_file = {'title': copy_title, 'name': copy_title}
        if parentid:
            copied_file['parents'] = [parentid]
        #print(copied_file)
        try:
            file = service.files().copy(fileId=origin_file_id, body=copied_file).execute()
            st.write('File copied: ' + file['name'] + ' - ' + file['id'])
            return file['id']

        except Exception as error:
            st.write('An error occurred: %s' % error)
        return None

    def create_folder(self, service, title, desc, parentid=None):
        body = {
            'name': title,
            'description': desc,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parentid:
            body['parents'] = [parentid]
        try:
            folder = service.files().create(body=body).execute()
            st.write('Folder created: ' + title + ' - ' + folder['id'])
            return folder['id']

        except Exception as error:
            st.write('An error occurred: %s' % error)
        return None

    def copy_folder(self, service, folder_id, folder_title, parentid=None, file_suffix=''):
        """Copy objects in folder including files and subfolders
        Args:
            service: Drive API service instance.
            folder_id: ID of the source folder
            folder_title: Title of the folder
            parentid: parent folder ID where the source folder is copied
        Returns:
            IDs of source and target folders
        """
        new_created_ids = []
        new_folderid = self.create_folder(service, folder_title, folder_title, parentid)
        new_created_ids.append({'src_id': folder_id, 'dest_id': new_folderid})
        # list of files and folders in source folder
        results = service.files().list(
            pageSize=10, fields="nextPageToken, files(id, name, mimeType, description)",
            q="'" + folder_id + "' in parents and trashed=false").execute()
        files = results.get('files', [])

        # recursively looping thru folders/subfolders and files
        for file in files:
            if file['mimeType'] == 'application/vnd.google-apps.folder':
                ### Use recursion to copy sub-folder
                sub_created_ids = self.copy_folder(service, file['id'], file['name'], parentid=new_folderid, file_suffix=file_suffix)
                new_created_ids += sub_created_ids
            else:
                ### copy file and suffix with customer name
                file_name = file['name']
                if file_suffix != '':
                    if file_name.find('.') >= 0:
                        file_name = file_name.replace('.', '_' + file_suffix + '.')
                    else:
                        file_name = file_name + '_' + file_suffix

                copied_fileid = self.copy_file(service, file['id'], file_name, parentid=new_folderid)
                new_created_ids.append({'src_id': file['id'], 'dest_id': copied_fileid})

        return new_created_ids


###################### Script main starts here ###################

st.set_page_config(page_title="MRA", page_icon=":tada:", layout="wide")
st.title("Migration Readiness Assessment (MRA)")
st.subheader("Application to create customer folder and copy documents from template")
st.write("Provide below details:")

with st.form(key='mra_form'):
	p_cust_name = st.text_input(label='Customer')
	p_sys_name = st.text_input(label='Legacy Platform')
	p_month = st.text_input(label='Month and Year')
	submit = st.form_submit_button(label='Submit')

if submit:
    st.write(f'Cust {p_cust_name}')
    st.write(f'Platform {p_sys_name}')
    st.write(f'Month {p_month}')

    if p_cust_name == '' or p_sys_name == '' or p_month == '':
        st.write("Please enter the mandatory fields!")
    else:
        #authentication and creating the service
        gdrive = gdrive()
        gservice = gdrive.get_gdrive_service()

        # check for folder existence
        cust_folder_id = gdrive.get_folder_id(gservice, p_cust_name, parentid=trg_root_id)
        #print(cust_folder_id)

        if cust_folder_id != None:
            st.write('Folder name "' + p_cust_name + '" already exists in target, please try differnt folder name!')
        else:
            st.write('Process Started..')

            #create customer folder
            trg_fold_id = gdrive.create_folder(gservice, p_cust_name, p_cust_name, parentid=trg_root_id)

            #get the files and file ids of the tempate folder
            src_dict = gdrive.get_file_dict(gservice, parentid=src_root_id)

            for src_folder in src_folders:
                # folder id of src_fold
                src_fold_id = src_dict[src_folder]
                trg_folder = src_folder.replace(v_sys_name, p_sys_name)
                trg_folder = trg_folder.replace(v_month, p_month)

                #copy system folder src_fold_id -> trg_fold_id
                folder_list = gdrive.copy_folder(gservice, src_fold_id, trg_folder, trg_fold_id, p_cust_name)
                print('Folder ' + src_folder + ' Copied!')

            #get the files and file ids of the customer folder
            trg_dict = gdrive.get_file_dict(gservice, parentid=trg_fold_id)

            st.write('Process Completed!')
