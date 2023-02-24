from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from djoser.views import UserViewSet
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (SAFE_METHODS, IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)

from .filters import IngredientSearchFilter, RecipesFilter
# from .mixin import CreateDestroyViewSet
from .pagination import LimitPageNumberPagination
from .permissions import IsAuthorOrReadOnly
from .serializers import (ShortRecipeSerializer, IngredientSerializer,
                          RecipeEditSerializer, RecipeSerializer,
                          SubscriptionSerializer, TagSerializer,
                          UserCreateSerializer, UserListSerializer)
# ShoppingCartSerializer,
from recipes.models import (FavoriteRecipe, Ingredient, Recipe, ShoppingCart,
                            Subscription, Tag)

User = get_user_model()


class CustomUserViewSet(UserViewSet):
    queryset = User.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserListSerializer

    def get_permission(self):
        if self.action == 'me':
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    @action(
        detail=False,
        permission_classes=(IsAuthenticated,))
    def subscription(self, request):
        queryset = Subscription.objects.filter(user=request.user)
        pages = self.paginate_queryset(queryset)
        serializer = SubscriptionSerializer(
            pages,
            many=True,
            context={'request': request},)
        return self.get_paginated_response(serializer.data)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)
    filter_backends = [IngredientSearchFilter]
    search_fields = ('^name',)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    permission_classes = (IsAuthorOrReadOnly,)
    filterset_class = RecipesFilter
    pagination_class = LimitPageNumberPagination

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return RecipeSerializer
        return RecipeEditSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=False,
        methods=('get',),
        url_path='download_shopping_cart')
    def download_file(self, request):
        user = request.user
        if not user.shopping_cart.exists():
            return Response(
                'В корзине нет товаров', status=status.HTTP_400_BAD_REQUEST)
        text = 'Список покупок: \n'
        ingredient_name = 'recipe__recipe__ingredient__name'
        ingredient_unit = 'recipe__recipe__ingredient__measurement_unit'
        recipe_amount = 'recipe__recipe__quantity'
        quantity_sum = 'recipe__recipe__quantity__sum'
        cart = user.shopping_cart.select_related('recipe').values(
            ingredient_name, ingredient_unit).annotate(Sum(
                recipe_amount)).order_by(ingredient_name)
        for product in cart:
            text += (
                f'{product[ingredient_name]} ({product[ingredient_unit]})'
                f' - {product[quantity_sum]}\n'
            )
        response = HttpResponse(text, content_typy='text/plain')
        filename = 'shopping_cart.txt'
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response

    def add_obj(self, model, user, pk):
        if model.objects.filter(user=user, recipe__id=pk).exists():
            return Response({
                'errors': 'Рецепт добавлен в список'
            }, status=status.HTTP_400_BAD_REQUEST)
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = ShortRecipeSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete_obj(self, model, user, pk):
        obj = model.objects.filter(user=user, recipe__id=pk)
        if obj.exists():
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({
            'errors': 'Рецепт удален'
        }, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=['POST', 'DELETE'],
        permission_classes=(IsAuthenticated,),)
    def favorite(self, request, pk=None):
        if request.method == 'POST':
            return self.add_obj(FavoriteRecipe, request.user, pk)
        if request.method == 'DELETE':
            return self.delete_obj(FavoriteRecipe, request.user, pk)
        return None

    @action(
        detail=True,
        methods=['POST', 'DELETE'],
        permission_classes=(IsAuthenticated,),)
    def shopping_cart(self, request, pk=None):
        if request.method == 'POST':
            return self.add_obj(ShoppingCart, request.user, pk)
        if request.method == 'DELETE':
            return self.delete_obj(ShoppingCart, request.user, pk)
        return None

    # @action(
    #     detail=False,
    #     methods=('get',),
    #     url_path='download_shopping_cart',
    #     pagination_class=None)
    # def download_file(self, request):
    #     user = request.user
    #     if not ShoppingCart.objects.filter(user_id=user.id).exists():
    #         return Response(
    #             'В корзине нет товаров', status=status.HTTP_400_BAD_REQUEST)

    #     ingredients = IngredientAmount.objects.filter(
    #         recipe__purchase__user=user
    #     )
    #     ingredients_value = ingredients.values(
    #         'ingredient__name',
    #         'ingredient__measurement_unit',
    #     ).annotate(amount=Sum('amount'))
    #     ready_list, filename = create_txt(user, ingredients_value)
    #     response = HttpResponse(ready_list, content_type='text/plain')
    #     response['Content-Disposition'] = f'attachment; filename={filename}'
    #     return response


# class SubscriptionViewSet(CreateDestroyViewSet):
#     serializer_class = SubscriptionSerializer

#     def paginate_queryset(self):
#         return self.request.user.follower.all()

#     def get_serializer_context(self):
#         context = super().get_serializer_context()
#         context['author_id'] = self.kwargs.get('user_id')
#         return context

#     def perform_create(self, serializer):
#         serializer.save(
#             user=self.request.user,
#             author=get_object_or_404(
#                 User,
#                 id=self.kwargs.get('user_id')
#             )
#         )

#     @action(methods=('delete',), detail=True)
#     def delete(self, request, user_id):
#         get_object_or_404(User, id=user_id)
#         if not Subscription.objects.filter(
#                 user=request.user, author_id=user_id).exists():
#             return Response({'errors': 'Вы не были подписаны на автора'},
#                             status=status.HTTP_400_BAD_REQUEST)
#         get_object_or_404(
#             Subscription,
#             user=request.user,
#             author_id=user_id
#         ).delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)


# class FavoriteRecipeViewSet(CreateDestroyViewSet):
#     serializer_class = FavoriteRecipeSerializer

#     def get_queryset(self):
#         user = self.request.user.id
#         return FavoriteRecipe.objects.filter(user=user)

#     def get_serializer_context(self):
#         context = super().get_serializer_context()
#         context['recipe_id'] = self.kwargs.get('recipe_id')
#         return context

#     def perform_create(self, serializer):
#         serializer.save(
#             user=self.request.user,
#             favorite_recipe=get_object_or_404(
#                 Recipe,
#                 id=self.kwargs.get('recipe_id')
#             )
#         )

#     @action(methods=('delete',), detail=True)
#     def delete(self, request, recipe_id):
#         user = request.user
#         if not user.favorite.select_related(
#                 'favorite_recipe').filter(
#                     favorite_recipe_id=recipe_id).exists():
#             return Response({'errors': 'Рецепт не в избранном'},
#                             status=status.HTTP_400_BAD_REQUEST)
#         get_object_or_404(
#             FavoriteRecipe,
#             user=request.user,
#             favorite_recipe_id=recipe_id).delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)


# class ShoppingCartViewSet(CreateDestroyViewSet):
#     serializer_class = ShoppingCartSerializer

#     def get_queryset(self):
#         user = self.request.user.id
#         return ShoppingCart.objects.filter(user=user)

#     def get_serializer_context(self):
#         context = super().get_serializer_context()
#         context['recipe_id'] = self.kwargs.get('recipe_id')
#         return context

#     def perform_create(self, serializer):
#         serializer.save(
#             user=self.request.user,
#             recipe=get_object_or_404(
#                 Recipe,
#                 id=self.kwargs.get('recipe_id')
#             )
#         )

#     @action(methods=('delete',), detail=True)
#     def delete(self, request, recipe_id):
#         user = request.user
#         if not user.shopping_cart.select_related(
#                 'recipe').filter(
#                     recipe_id=recipe_id).exists():
#             return Response({'errors': 'Рецепта нет в корзине'},
#                             status=status.HTTP_400_BAD_REQUEST)
#         get_object_or_404(
#             ShoppingCart,
#             user=request.user,
#             recipe=recipe_id).delete()
#         return Response(status=status.HTTP_204_NO_CONTENT)
