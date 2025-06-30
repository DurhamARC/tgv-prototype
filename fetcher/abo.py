from datasource import DataSource

import json
import logging
import os
import shutil
import tqdm

import utils

PROJECT_ID = "ABO"
SOURCE_ID = "iiif.onb.ac.at"
IIIF_MANIFEST_URL = f"https://{SOURCE_ID}" + "/presentation/{project}/{id}/manifest"

class ABODataSource(DataSource):
    """
    Data source for fetching IIIF manifests and resources from the 
    Austrian National Library ABO (Austrian Books Online) IIIF service.
    """
    def __init__(self, 
                 source_id: str = SOURCE_ID, 
                 manifest_url: str = IIIF_MANIFEST_URL, 
                 project_id: str = PROJECT_ID, 
                 cache_name: str = "devel"):
        """
        Initialize the data source

        :param manifest_url: URL template for the IIIF manifest
        :param source_id: Source ID for the data source
        :param project_id: Project ID for the data source
        :param cache_name: Name of the cache for requests
        """

        self.source_id = source_id
        self.manifest_url = manifest_url
        self.project_id = project_id

        super().__init__(source_id, cache_name)

    def fetch(self, item_id: str):
        
        os.makedirs(f"data/{self.source_id}/{self.project_id}", exist_ok=True)
        
        item_dir = os.path.join('data', self.source_id, self.project_id)
        os.makedirs(item_dir, exist_ok=True)

        # Check if item_id directories already exist
        already = utils.list_directories(f"data/{self.source_id}/{self.project_id}")
        if item_id not in already:
            item_dir = os.path.join('data', self.source_id, self.project_id, item_id)
            try:
                self._download_files(item_id, item_dir, resource_format="text/plain")
            except (TypeError, ValueError) as e:
                logging.error(f"Failed to download files for item ID {item_id}: {e}")


    def _download_files(self, item_id, output_dir, resource_format):
        os.makedirs(output_dir, exist_ok=True)

        manifest_url = self.manifest_url.format(project=self.project_id, id=item_id)
        
        if self.session is None:
            raise ValueError("Session is not initialized. Call connect() first.")
        
        manifest = self.session.get(manifest_url).json()

        if "sequences" not in manifest:
            if "message" in manifest:
                # Remove the output directory if the manifest is not valid
                logging.debug(f"Removing output directory due to invalid manifest for {item_id}")
                shutil.rmtree(output_dir)
                raise ValueError(f"Error fetching manifest: {manifest['message']}")

        json_dir = os.path.join(output_dir, 'json')
        os.makedirs(json_dir, exist_ok=True)
        manifest_filename = os.path.join(output_dir, 'json', 'manifest.json')
        with open(manifest_filename, 'w', encoding='utf-8') as manifest_file:
            json.dump(manifest, manifest_file, ensure_ascii=False, indent=4)

        for sequence in manifest['sequences']:
            for canvas in tqdm.tqdm(sequence['canvases']):
                label = canvas['label']
                for content in canvas.get('otherContent', []):
                    for resource in content.get('resources', []):
                        resource_id = resource['resource']['@id']
                        format = resource['resource']['format']

                        if format == resource_format:
                            response = self.session.get(resource_id)
                            extension = 'txt' if resource_format == 'text/plain' else 'html'
                            
                            ext_dir = os.path.join(output_dir, extension)
                            os.makedirs(ext_dir, exist_ok=True)
                            
                            filename = os.path.join(output_dir, extension, f"{label}.{extension}")
                            
                            with open(filename, 'wb') as file:
                                file.write(response.content)
                            
                            logging.debug(f"Downloaded {extension.upper()} file for {label} to {filename}")

    @staticmethod
    def process(file_path, data_directory):
        SOURCE_ID = "iiif.onb.ac.at"

        parts = file_path.split(os.sep)
        title_id = parts[3]
        project_id = parts[2]
        label = parts[-1].split('.')[0]
        
        with open(os.path.join(data_directory, SOURCE_ID, project_id, title_id, 'json', 'manifest.json'), 'r', encoding='utf-8') as file:
            manifest = json.load(file)
        
        title_full = manifest['label']

        remote_path = None
        image_url = None
        for sequence in manifest['sequences']:
            for canvas in sequence['canvases']:
                if label == canvas['label']:
                    for content in canvas.get('otherContent', []):
                        for resource in content.get('resources', []):
                            if resource['resource']['format'] == 'text/plain':
                                remote_path = resource['resource']['@id']
                                break
                    for image in canvas['images']:
                        original_image_url = image['resource']['@id']
                        image_url = original_image_url.replace('/full/full/', '/full/,2400/')
                        break

        with open(file_path, 'r') as file:
            ocr_text = file.read()

        ocr_text_stripped = utils.remove_newlines(ocr_text)

        return {
            "local_path": file_path,
            "source": SOURCE_ID,
            "title_id": title_id,
            "title_full": title_full,
            "date": "n.d.",
            "page_number": "(" + label.replace("page", "") + ")",
            "remote_path": remote_path,
            "image_url": image_url,
            "ocr_text_original": ocr_text,
            "ocr_text_stripped": ocr_text_stripped,
        }
    

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Download HOCR files for given item ID.")
    parser.add_argument("item_id", type=str, help="The item ID to download HOCR files for.")
    args = parser.parse_args()

    data_source = ABODataSource(manifest_url=IIIF_MANIFEST_URL, project_id=PROJECT_ID, source_id=SOURCE_ID)
    data_source.fetch(args.item_id)
