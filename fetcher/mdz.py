from datasource import DataSource

import json
import logging
import os
import tqdm

import utils

SOURCE_ID = "api.digitale-sammlungen.de"
IIIF_MANIFEST_URL = f"https://{SOURCE_ID}" + "/iiif/presentation/v2/{id}/manifest"

class MDZDataSource(DataSource):

    def __init__(self, 
                 source_id: str = SOURCE_ID, 
                 manifest_url: str = IIIF_MANIFEST_URL, 
                 cache_name: str = "devel"):

        self.source_id = source_id
        self.manifest_url = manifest_url
        
        super().__init__(source_id=source_id, cache_name=cache_name)

    def fetch(self, item_id: str):

        item_dir = os.path.join('data', self.source_id)
        os.makedirs(item_dir, exist_ok=True)        

        already = utils.list_directories(f"data/{self.source_id}")
        if item_id not in already:
            item_dir = os.path.join('data', self.source_id, item_id)
            os.makedirs(item_dir, exist_ok=True)
            self._download_hocr_files(item_id=item_id, output_dir=item_dir)
        
            input_dir = os.path.join(item_dir, 'hocr')
            output_dir = os.path.join(item_dir, 'txt')
            os.makedirs(output_dir, exist_ok=True)
            utils.convert_all_hocr_files(input_dir, output_dir)

    def _download_hocr_files(self, item_id, output_dir):
        os.makedirs(output_dir, exist_ok=True)

        manifest_url = self.manifest_url.format(id=item_id)
        manifest = self.session.get(manifest_url).json()
        
        json_dir = os.path.join(output_dir, 'json')
        os.makedirs(json_dir, exist_ok=True)
        manifest_filename = os.path.join(json_dir, 'manifest.json')
        with open(manifest_filename, 'w', encoding='utf-8') as manifest_file:
            json.dump(manifest, manifest_file, ensure_ascii=False, indent=4)

        hocr_dir = os.path.join(output_dir, 'hocr')
        os.makedirs(hocr_dir, exist_ok=True)
      
        for sequence in manifest['sequences']:
            for canvas in tqdm.tqdm(sequence['canvases'], desc=f"Downloading {item_id}"):
                label = canvas['label']
                hocr_url = canvas['seeAlso']['@id']
                
                hocr_response = self.session.get(hocr_url)
                hocr_filename = os.path.join(hocr_dir, f"{label}.hocr")
                
                with open(hocr_filename, 'wb') as file:
                    file.write(hocr_response.content)
                
                logging.info(f"Downloaded HOCR file for {label} to {hocr_filename}")

    @staticmethod
    def process(file_path, data_directory):
        SOURCE_ID = "api.digitale-sammlungen.de"
        
        parts = file_path.split(os.sep)
        title_id = parts[2]
        label = parts[-1].split('.')[0]

        with open(os.path.join(data_directory, SOURCE_ID, title_id, 'json', 'manifest.json'), 'r', encoding='utf-8') as file:
            manifest = json.load(file)
        
        title_full = manifest['label']

        structures = manifest.get("structures", None)
        canvas_to_structure_label = {}

        if structures:
            for structure in structures:
                canvases = structure.get("canvases", [])
                for canvas in canvases:
                    canvas_to_structure_label[canvas] = structure["label"]

        remote_path = None
        image_url = None
        for sequence in manifest['sequences']:
            for canvas in sequence['canvases']:
                if label == canvas['label']:
                    date = canvas_to_structure_label.get(canvas['@id'], "n.d.")
                    remote_path = canvas['seeAlso']['@id']
                    for image in canvas['images']:
                        original_image_url = image['resource']['@id']
                        image_url = original_image_url.replace('/full/full/', '/full/2400,/')
                        break
        
        with open(file_path, 'r') as file:
            ocr_text = file.read()

        ocr_text_stripped = utils.remove_newlines(ocr_text)

        return {
            "local_path": file_path,
            "source": SOURCE_ID,
            "title_id": title_id,
            "title_full": title_full,
            "date": date,
            "page_number": label,
            "remote_path": remote_path,
            "image_url": image_url,
            "ocr_text_original": ocr_text,
            "ocr_text_stripped": ocr_text_stripped,
        }

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Download HOCR files for given item IDs.")
    parser.add_argument("item_id", type=str, help="The item ID to download HOCR files for.")
    args = parser.parse_args()

    data_source = MDZDataSource(source_id=SOURCE_ID, manifest_url=IIIF_MANIFEST_URL)
    data_source.fetch(args.item_id)
