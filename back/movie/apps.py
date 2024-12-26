from django.apps import AppConfig

from django.db.models.signals import post_migrate
from django.dispatch import receiver
import os
import re
import pandas as pd
import requests
from traitlets import default
from pprint import pprint
from functools import partial

# apps.py 의 역할
# Django 애플리케이션의 설정과 초기화 로직을 정의하는 곳
# 애플리케이션이 로드될 때 특정 작업(신호 연결, 데이터 초기화) 수행

# apps.py의 실행흐름
# 1. Django가 애플리케이션을 로드할 때:
# - INSTALLED_APPS에 등록된 각 애플리케이션의 AppConfig 클래스가 실행된다.
# - AppConfig의 ready() 메서드가 호출됨
# - 여기서 초기화 작업(신호 연결, 데이터 로드)를 수행함.

# ready()의 사용 예시:
# - 신호(signals) 연결
# - 데이터 초기화.
# - 외부 서비스와 초기 통신 설정.

# AppConfig
# :Django가 각 애플리케이션을 관리하기 위한 기본 클래스 

# MovieConfig 
# :AppConfig를 상속받아 movie 애플리케이션의 설정을 정의한 커스텀 클래스.
class MovieConfig(AppConfig):

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'movie'
    # Django가 이 name으로 애플리케이션을 식별함함

    def ready(self):
        from .models import Genre, Movie, Script
        from django.conf import settings

        # apps.py의 ready 함수
        # movie 앱이 처음 시작될 때 수행되는 함수
        
        # Django의 Signals : 특정 이벤트가 발생했을 때 미리 정의된 핸들러 함수를 실행하도록 하는 Observer 패턴의 구현
        # 애플리케이션의 특정 동작에 대해 자동으로 반응할 수 있는 좋은 도구.
        # 해당 app에 signals.py를 만들어 커스털 signal을 정의할 수 있음.

        # Observer 패턴이란
        # : 객체의 상태 변화를 다른 객체들이 감지하고 처리하는 디자인 패턴(Django의 Signals, Spring의 이벤트 시스템, UI 업데이트 시스템)

        # signal.connect(receiver, sender, **kwargs)
        # signal : 연결할 signal 객체
        # receiver : signal이 발생할 때 호출할 함수 또는 메서드
        # sender : signal을 발신하는 객체를 지정. sender를 지정하지 않으면 모든 sender에 대해 signal을 처리함.

        # post_migrate 시그널은 데이터베이스 초기화 작업이나 기본 데이터를 삽입하는데 자주 사용됨.
        post_migrate.connect(self.load_vocabulary, sender=self)
        # post_migrate라는 signal이 발생할 때 self.load_vocabulary 라는 함수를 호출하도록 연결하는 코드
        # sender=self 는 현재 클래스(MovieConfig)를 sender로 지정한 것이고, 이 의미는 MovieConfig 앱에 대한 post_migrate 시그널이
        # 발생했을 때 이 함수가 호출된다는 뜻

        # partial을 사용해 인자 미리 설정
        load_genres_partial = partial(self.load_genres, Genre=Genre)
        load_movies_partial = partial(self.load_movies, Movie=Movie, Genre=Genre, api_key=settings.TMDB_API_KEY)
        load_subtitles_partial = partial(self.load_subtitles, Movie=Movie, Script=Script, api_key=settings.OPENSUBTITLES_API_KEY)

        post_migrate.connect(load_genres_partial, sender=self)
        post_migrate.connect(load_movies_partial, sender=self)
        post_migrate.connect(load_subtitles_partial, sender=self)
        

    def load_vocabulary(self, sender, **kwargs):
        from .models import VocabularyWord, Genre, Movie, Script
        from django.conf import settings

        self.load_toeic_voca(VocabularyWord)
        self.load_sat_voca(VocabularyWord)
        self.load_business_voca(VocabularyWord)
        self.load_daily_voca(VocabularyWord)

        print("끝")

        # # 이 부분은 SRP 원칙을 어긴 코드
        # # 원래 하나의 함수는 관련된 하나의 기능을 하는게 맞음. 지금은 load_vocabulary 함수에 genre도 load하고 movie, subtitles도 load하고 있음
        # # ready 함수에 post_migrate.connect() 를 나눠서 적어야함
        # self.load_genres(Genre)

        # self.load_movies(Movie, Genre, settings.TMDB_API_KEY)
        # self.load_subtitles(Movie, Script, settings.OPENSUBTITLES_API_KEY)

    def load_toeic_voca(self, VocabularyWord):
        # 파일 경로 설정 (여기서 경로는 파일의 실제 위치에 맞게 수정하세요)
        file_path = os.path.join(os.path.dirname(
            __file__), 'voca/toeic/toeic_1.txt')
        category = 'TOEIC'

        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='cp949') as file:
                for line in file:
                    match = re.match(
                        r'^\d+\.\s+([a-zA-Z]+)\s+(.+)', line.strip())
                    if match:
                        word = match.group(1)
                        meaning = match.group(2)

                        # DB에 단어가 없다면 추가
                        if not VocabularyWord.objects.filter(word=word, category=category).exists():
                            VocabularyWord.objects.create(
                                word=word, meaning=meaning, category=category)
                            print(f'생성된 단어 : {word} - {meaning}')
                        else:
                            print(f'단어가 이미 존재합니다: {word}')
        else:
            print(f"파일 {file_path} 이 존재하지 않습니다.")

    def load_sat_voca(self, VocabularyWord):
        file_paths = [
            os.path.join(os.path.dirname(__file__), 'voca/SAT/sat_1.xlsx'),
            os.path.join(os.path.dirname(__file__), 'voca/SAT/sat_2.xlsx'),
            os.path.join(os.path.dirname(__file__), 'voca/SAT/sat_3.xlsx')
        ]

        for file_path in file_paths:
            try:
                df = pd.read_excel(file_path)
                for index, row in df.iterrows():
                    word = row.iloc[1]  # 영어단어가 두 번째 열에 있다고 가정
                    meaning = row.iloc[2]  # 뜻은 세 번째 열에

                    word = word.strip() if isinstance(word, str) else None
                    meaning = meaning.strip() if isinstance(meaning, str) else None

                    # 영어 단어로만 구성된 경우 추가
                    if word and re.match(r'^[a-zA-Z]+$', word):
                        try:
                            vocabulary, created = VocabularyWord.objects.get_or_create(
                                word=word, category='SAT', defaults={'meaning': meaning})
                            if created:
                                print(f'Added SAT word: {word}')
                        except Exception as e:
                            print(f'SAT word already exists: {word}')
            except Exception as e:
                print(f"Error processing file {file_path}: {e}")

    def load_business_voca(self, VocabularyWord):
        file_paths = [
            os.path.join(os.path.dirname(__file__),
                         'voca/business/business.xlsx'),
        ]

        for file_path in file_paths:
            try:
                df = pd.read_excel(file_path)
                for index, row in df.iterrows():
                    word = row.iloc[1]
                    meaning = row.iloc[2]

                    word = word.strip() if isinstance(word, str) else None
                    meaning = meaning.strip() if isinstance(meaning, str) else None

                    # 영어 단어로만 구성된 경우 추가
                    if word and re.match(r'^[a-zA-Z]+$', word):
                        try:
                            vocabulary, created = VocabularyWord.objects.get_or_create(
                                word=word, category='BUSINESS', defaults={'meaning': meaning})
                            if created:
                                print(f'비즈니스 영단어: {word}')
                        except Exception as e:
                            print(f'비즈니스 word already exists: {word}')
            except Exception as e:
                print(f"Error processing file {file_path}: {e}")

    def load_daily_voca(self, VocabularyWord):
        file_paths = [
            os.path.join(os.path.dirname(__file__), 'voca/daily/daily.xlsx'),
        ]

        for file_path in file_paths:
            try:
                # 엑셀 파일 읽기
                df = pd.read_excel(file_path)

                # 데이터 처리
                for index, row in df.iterrows():
                    combined = row.iloc[1]  # 단어와 뜻이 함께 있는 열

                    if isinstance(combined, str):  # 문자열인 경우에만 처리
                        # 수정된 정규식으로 단어와 뜻 분리
                        match = re.match(r'^\s*([a-zA-Z]+)\s+(.+)', combined)
                        if match:
                            word = match.group(1).strip()  # 영어 단어
                            meaning = match.group(2).strip()  # 뜻

                            # 데이터베이스에 저장
                            try:
                                vocabulary, created = VocabularyWord.objects.get_or_create(
                                    word=word, category='DAILY', defaults={'meaning': meaning}
                                )
                                if created:
                                    print(f'추가된 일상 단어: {word}')
                            except Exception as e:
                                print(f'이미 존재하는 단어: {word}, 오류: {e}')
                        else:
                            print(f'형식이 올바르지 않은 데이터: {combined}')
            except Exception as e:
                print(f"파일 처리 중 오류 발생 {file_path}: {e}")

    def load_genres(self, Genre, sender, **kwargs):
        # TMDB 장르 데이터
        genres = [
            {'id': 28, 'name': 'Action'},
            {'id': 12, 'name': 'Adventure'},
            {'id': 16, 'name': 'Animation'},
            {'id': 35, 'name': 'Comedy'},
            {'id': 80, 'name': 'Crime'},
            {'id': 99, 'name': 'Documentary'},
            {'id': 18, 'name': 'Drama'},
            {'id': 10751, 'name': 'Family'},
            {'id': 14, 'name': 'Fantasy'},
            {'id': 36, 'name': 'History'},
            {'id': 27, 'name': 'Horror'},
            {'id': 10402, 'name': 'Music'},
            {'id': 9648, 'name': 'Mystery'},
            {'id': 10749, 'name': 'Romance'},
            {'id': 878, 'name': 'Science Fiction'},
            {'id': 10770, 'name': 'TV Movie'},
            {'id': 53, 'name': 'Thriller'},
            {'id': 10752, 'name': 'War'},
            {'id': 37, 'name': 'Western'},
        ]

        # DB에 장르 데이터 삽입
        for genre in genres:
            Genre.objects.get_or_create(id=genre['id'], name=genre['name'])
            print(f"장르 데이터 추가됨: {genre['name']}")

    def load_movies(self, Movie, Genre, api_key, sender, **kwargs):
        url = "https://api.themoviedb.org/3/discover/movie"
        movies_to_fetch = 15  # 가져올 총 영화 수 조절 가능
        movies_fetched = 0
        page = 1

        params = {
            'api_key': api_key,
            'language': 'ko-KR',
        }

        try:
            while movies_fetched < movies_to_fetch:
                params['page'] = page  # 페이지 설정
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    movies_data = response.json().get('results', [])
                    if not movies_data:  # 더 이상 결과가 없으면 중단
                        break

                    for movie_data in movies_data:
                        if movies_fetched >= movies_to_fetch:  # 필요한 만큼 가져왔으면 종료
                            break

                         # 영화 상세 정보 가져오기
                        detail_url = f"https://api.themoviedb.org/3/movie/{movie_data['id']}"
                        detail_response = requests.get(detail_url, params={
                            'api_key': api_key,
                            'language': 'ko-KR',
                            'append_to_response': 'credits,release_dates'
                        })

                        if detail_response.status_code == 200:
                            detail_data = detail_response.json()
                            credits_data = detail_data.get('credits', {})

                            # 감독 찾기
                            director = next((crew['name'] for crew in credits_data.get('crew', [])
                                             if crew['job'] == 'Director'), None)

                            # 주요 출연진 (상위 5명)
                            cast = [{'name': actor['name'], 'character': actor['character']}
                                    for actor in credits_data.get('cast', [])[:5]]

                            # 등급 찾기 (미국 등급 기준)
                            rating = None
                            for country in detail_data.get('release_dates', {}).get('results', []):
                                if country['iso_3166_1'] == 'US':
                                    for release in country['release_dates']:
                                        if release.get('certification'):
                                            rating = release['certification']
                                            break
                                    break

                            movie, created = Movie.objects.get_or_create(
                                tmdb_id=movie_data['id'],
                                defaults={
                                    'title': movie_data['title'],
                                    'poster_path': f"https://image.tmdb.org/t/p/w500{movie_data['poster_path']}",
                                    'backdrop_path': f"https://image.tmdb.org/t/p/original{movie_data.get('backdrop_path')}" if movie_data.get('backdrop_path') else None,
                                    'overview': movie_data['overview'],
                                    'release_date': movie_data['release_date'],
                                    'runtime': detail_data.get('runtime'),
                                    'rating': rating,
                                    'director': director,
                                    'cast': cast
                                }
                            )

                            for genre_id in movie_data.get('genre_ids', []):
                                genre = Genre.objects.filter(
                                    id=genre_id).first()
                                if genre:
                                    movie.genres.add(genre)

                            movies_fetched += 1  # 가져온 영화 수 증가

                    page += 1  # 다음 페이지로 이동
                else:
                    print(f"Error: {response.status_code}")
                    break
        except Exception as e:
            print(f"Error loading movies: {e}")

    def load_subtitles(self, Movie, Script, api_key, sender, **kwargs):
        from .subtitle_utils import parse_srt, classify_difficulty_level, save_subtitle_to_db
        import time

        headers = {
            'Api-Key': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'movie v1.0'
        }

        total_movies = Movie.objects.count()
        current_movie = 0

        for movie in Movie.objects.all():
            current_movie += 1
            print(f"\nProcessing movie {current_movie}/{total_movies}")

            if not Script.objects.filter(movie=movie).exists():
                print(f"Fetching subtitles for: {movie.title}...")
                try:
                    # 자막 검색
                    search_url = f"https://api.opensubtitles.com/api/v1/subtitles?tmdb_id={movie.tmdb_id}&languages=en"
                    response = requests.get(search_url, headers=headers)

                    if response.status_code == 200:
                        subtitles_data = response.json().get('data', [])
                        if subtitles_data:
                            file_id = subtitles_data[0]['attributes']['files'][0]['file_id']
                            print(f"해킹중.. for {movie.title}.")

                            # 다운로드
                            download_url = "https://api.opensubtitles.com/api/v1/download"
                            download_response = requests.post(
                                download_url, headers=headers, json={"file_id": file_id})

                            if download_response.status_code == 200:
                                subtitle_link = download_response.json().get('link', '')
                                subtitle_response = requests.get(subtitle_link)

                                if subtitle_response.status_code == 200:
                                    subtitle_content = subtitle_response.text
                                    subtitles = parse_srt(subtitle_content)
                                    save_subtitle_to_db(movie, subtitles)
                                    print(f"해킹 완료.. for: {movie.title}")
                                else:
                                    print(
                                        f"✗ Failed to download subtitle content for: {movie.title}")
                        else:
                            print(f"✗ No subtitles found for: {movie.title}")

                    # API 요청 제한을 고려하여 각 요청 사이에 딜레이 추가
                    time.sleep(1)  # 1초 대기

                except Exception as e:
                    print(
                        f"✗ Error processing subtitles for {movie.title}: {e}")
                    time.sleep(1)  # 에러 발생시에도 대기
            else:
                print(f"Skipping {movie.title} - subtitles already exist")
