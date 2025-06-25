from datasource import DataSource

import logging
import os
import tqdm

import utils 

SOURCE_ID = "anno.onb.ac.at"

class AnnoDataSource(DataSource):
    """
    Data source for fetching annotations from the Austrian National Library (ONB) (Austrian Newspapers Online) IIIF service.
    """

    def __init__(self,
                 source_id: str = SOURCE_ID, 
                 cache_name: str = "devel"):
        """
        Initialize the data source
        
        :param manifest_url: URL template for the IIIF manifest
        :param source_id: Source ID for the data source
        :param project_id: Project ID for the data source
        :param cache_name: Name of the cache for requests
        """

        self.base_url = f"https://{source_id}"
        self.text_url = "{base_url}/cgi-content/annoshow?text={title_id}|{datum}|{page_number}"
        self.image_url = "{base_url}/cgi-content/annoshow?call={title_id}|{datum}|{page_number}|{zoom_level}"

        super().__init__(source_id=source_id, cache_name=cache_name)
    
    def fetch(self, 
              title_id: str,
              minimum: int, 
              maximum: int, 
              list_available: bool = False):
        
        valid_datums = self._get_valid_datums(title_id)

        if minimum:
            valid_datums = [d for d in valid_datums if d >= minimum]
        if maximum:
            valid_datums = [d for d in valid_datums if d <= maximum]

        if list_available:
            valid_datums.sort()
            for datum in valid_datums:
                logging.info(datum)
            return
        
        folder = f"data/{self.source_id}/{title_id}"
        os.makedirs(folder, exist_ok=True)

        already = utils.list_directories(folder)
        already = [int(d) for d in already if d.isdigit()]
        missing = list(set(valid_datums) - set(already))

        if len(missing) == 0:
            return
        
        for vd in tqdm.tqdm(missing):
            try:
                path_on_disk = self._get_text_for_datum(title_id, vd, page_number='x')
                utils.split_anno_x_file(path_on_disk, f"{folder}/{vd}/txt")
                utils.delete_file(path_on_disk)
            except FileNotFoundError as e:
                logging.error(f"File disappeared while processing {path_on_disk}")
                logging.error(e)

    def _get_valid_datums(self, title_id: str):
        title_url = self.base_url + f"/cgi-content/anno?apm=0&aid={title_id}"
        all_hrefs = utils.get_all_hrefs(title_url, session=self.session)
        year_hrefs = [f"{self.base_url}{h}" for h in all_hrefs if ('datum=' in h)]

        all_ymd_hrefs = []
        for yh in year_hrefs:
            ah = utils.get_all_hrefs(yh, session=self.session)
            all_ymd_hrefs.extend(h for h in ah if ('datum=' in h))

        valid_datums = [utils.get_query_value(u, key='datum') for u in all_ymd_hrefs]
        valid_datums = list(set(valid_datums))
        valid_datums = [int(d) for d in valid_datums if d.isdigit()]

        return valid_datums

    def _get_text_for_datum(self, title_id, datum, page_number='x'):
        vd_uri = self.text_url.format(base_url=self.base_url, title_id=title_id, datum=datum, page_number=page_number)
        folder = f"data/{self.source_id}/{title_id}/{datum}/txt"
        path_on_disk = folder + '/' + f"{self.source_id}_{title_id}_{datum}.txt"
        utils.download_remote_file(vd_uri, path=path_on_disk, session=self.session)
        return path_on_disk

    @staticmethod
    def process(file_path, data_directory):
        SOURCE_ID = "anno.onb.ac.at"
        TEXT_URL = "https://anno.onb.ac.at/cgi-content/annoshow?text={title_id}|{datum}|{page_number}"
        IMAGE_URL= "https://anno.onb.ac.at/cgi-content/annoshow?call={title_id}|{datum}|{page_number}|{zoom_level}"

        TITLE_MAP = {
            'sam': 'Der Sammler. Ein Unterhaltungsblatt',
            'vlb': 'Vaterländische Blätter'
        }

        parts = file_path.split(os.sep)
        title_id = parts[2]
        datum = parts[3]
        page_number = parts[-1].split('.')[0]

        remote_path = TEXT_URL.format(title_id=title_id, datum=datum, page_number=page_number)
        image_url = IMAGE_URL.format(title_id=title_id, datum=datum, page_number=page_number, zoom_level='100')

        ocr_text = utils.read_multi_encoding(file_path)
        ocr_text_stripped = utils.remove_newlines(ocr_text)

        return {
            "local_path": file_path,
            "source": SOURCE_ID,
            "title_id": title_id,
            "title_full": TITLE_MAP[title_id],
            "datum": datum,
            "date": utils.datum_to_iso_8601(datum),
            "page_number": "(" + page_number + ")",
            "remote_path": remote_path,
            "image_url": image_url,
            "ocr_text_original": ocr_text,
            "ocr_text_stripped": ocr_text_stripped,
        }


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Fetch text for a given title_id and optional date range.")
    parser.add_argument("title_id", type=str, help="The title ID to fetch data for.")
    parser.add_argument("--min", type=int, help="The minimum date in YYYYMMDD format.", default=None)
    parser.add_argument("--max", type=int, help="The maximum date in YYYYMMDD format.", default=None)
    parser.add_argument("--list-available", action="store_true", help="List all valid datums in alphabetical order.")
    
    args = parser.parse_args()
    
    data_source = AnnoDataSource(source_id=SOURCE_ID)
    data_source.fetch(
        args.title_id, 
        minimum=args.min, 
        maximum=args.max,
        list_available=args.list_available)
