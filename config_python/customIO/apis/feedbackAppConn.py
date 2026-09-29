from googleapiclient.discovery import build
from google.oauth2 import service_account
from authlib.jose import jwt
import requests
import time as t


def create_date_condition(
        start_date: str = None,
        end_date: str = None,
        yesterday_date: str = None
    ):
    """
    Retourne une condition sous forme de fonction, pour tester si une date str est dans l'intervalle [start_date, end_date]
    ou après yesterday_date.

    Args:
        start_date (str, optional): Début de l'intervalle (inclus, UNIX ou ISO).
        end_date (str, optional): Fin de l'intervalle (inclus, UNIX ou ISO).
        yesterday_date (str, optional): Date de la veille (UNIX ou ISO).

    Returns:
        function: Fonction lambda testant si une date (UNIX ou ISO) respecte la condition.
    """
    if start_date and end_date:
        return lambda x: start_date <= x <= end_date
    elif yesterday_date:
        return lambda x: x > yesterday_date
    else:
        raise ValueError("Combinaison d'arguments invalide. Veuillez fournir soit (start_date et end_date) ou yesterday_date.")


class AndroidFeedback():
    """
    Permet de se connecter à l'api androidpiblisher.

    Args:
        sa_key: Utilise la clé d'un service account autorisé par l'api. A renseigner en cas de test local. (None par défaut)
        scopes (list): scopes nécessaires au service account pour accéder à l'api. Par défaut ['https://www.googleapis.com/auth/androidpublisher'].
    """
    def __init__(
            self,
            sa_key: dict,
            scopes=['https://www.googleapis.com/auth/androidpublisher']
        ):
        
        self.credentials = service_account.Credentials.from_service_account_info(
            sa_key,
            scopes=scopes
        )

    def get_api_response(self, package_name, max_results=100, token=None) -> dict:
        """
        Retrouve les reviews Android app store avec un package et le credential local.

        Args:
            package_name (str): Le nom du package de l'application.

        Returns:
            dict: La réponse de l'API Android Publisher, ou None si une erreur se produit.
        """

        androidpublisher = build('androidpublisher', 'v3', credentials=self.credentials)
        request = androidpublisher.reviews().list(
            packageName=package_name,
            maxResults=max_results,
            token=token
        )
        return request.execute()

    def get_reviews(
        self,
        response: dict,
        start_date: str = None,
        end_date: str = None,
        yesterday_date: str = None
        ):
        """Retrouve les commentaires des users le l'app Android de la veille ou selon un intervalle de temps,
        les commentaires datent d'une semaine max.
        https://developers.google.com/resources/api-libraries/documentation/androidpublisher/v3/python/latest/androidpublisher_v3.reviews.html

        Args:
            start_date (str): date de début des commentaires (inclus), format Timestamp Unix.
            end_date (str): date de fin des commentaires (inclus), format Timestamp Unix.
            yesterday (str): date de la veille, format Timestamp Unix.

        Returns:
            dict: La réponse de l'API Android Publisher, ou None si une erreur se produit.
        """
        condition = create_date_condition(start_date, end_date, yesterday_date)

        for review in response["reviews"]:
            for comment in review["comments"]:
                # Si la review est à la bonne date, la review est retournée
                try:
                    comment_date = comment["userComment"]["lastModified"]["seconds"]
                    if condition(comment_date):
                        yield review
                        break
                except KeyError:
                    continue


class IosFeedback():
    def __init__(
            self,
            token_duration: float,
            key_id: str,
            issuer_id: str,
            private_key: str
        ):

        expriration_time = int(round(t.time() + token_duration))

        header = {
            "alg": "ES256",
            "kid": key_id,
            "typ": "JWT"
        }
        payload = {
            "iss": issuer_id,
            "exp": expriration_time,
            "aud": "appstoreconnect-v1"
        }
        token = jwt.encode(header, payload, private_key)
        jwt_object = 'Bearer ' + token.decode()
        self.jwt_header = {'Authorization': jwt_object}

        t.sleep(5)

        self.ls_reviews = []

    def get_last_reviews(
            self,
            url: str,
            start_date: str = None,
            end_date: str = None,
            yesterday_date: str = None
        ) -> list:
        """
        Crée une condition en fonction des paramètres.
        Requête l'ios appstore sur les 50 derniers commentaires,
        si la date de fin n'est pas trouvé dans ce batch,
        la fonction se rappelle avec les 50 prochaines pages.
        
        Args:
            url (str): URL de la requête vers l'API de l'App Store pour les commentaires.
            start_date (str, optional): Date de début des commentaires (incluse),
                                       format Timestamp Unix (chaîne de caractères).
                                       Par défaut None.
            end_date (str, optional): Date de fin des commentaires (incluse),
                                     format Timestamp Unix (chaîne de caractères).
                                     Par défaut None.
            yesterday_date (str, optional): Date de la veille, format Timestamp Unix
                                           (chaîne de caractères). Utilisée comme date de début
                                           par défaut pour la logique de pagination si
                                           `start_date` n'est pas fourni. Par défaut None.
            ls_reviews (list): Liste utilisée en interne pour accumuler les
                                        commentaires lors des appels récursifs.
                                        Ne devrait généralement pas être fournie par
                                        l'appelant initial. Par défaut [].

        Returns:
            list: Une liste de dictionnaires. Chaque dictionnaire contient les attributs
                  ('attributes') d'un commentaire qui correspond aux critères de date
                  spécifiés. Retourne une liste vide si aucun commentaire ne correspond
                  ou si une erreur se produit lors de la requête.
        """
        condition = create_date_condition(start_date, end_date, yesterday_date)

        response = requests.get(url=url, headers=self.jwt_header)
        raw_reviews = response.json()

        # turn the page if date is upper start_date. If it's equal, the date of the first review is on the page so, no need to get another page.
        if raw_reviews.get('data') and raw_reviews['data'][-1]["attributes"]["createdDate"] > (start_date or yesterday_date):
            self.ls_reviews += [d["attributes"] for d in raw_reviews['data']]
            # check if there is a next page
            next_page_url = raw_reviews.get('links').get('next')
            print(f"----> next url {next_page_url}")
            print(self.ls_reviews[:2])
            
            if next_page_url:
                return self.get_last_reviews(
                    url=next_page_url,
                    start_date=start_date,
                    end_date=end_date,
                    yesterday_date=yesterday_date,
                )

        elif raw_reviews.get('data'):
            for d in raw_reviews.get('data'):
                # Only take the reviews in the date interval
                if condition(d["attributes"]["createdDate"]):
                    self.ls_reviews.append(d["attributes"])
                else:
                    break
            
            return self.ls_reviews
        
        else:
            return None
