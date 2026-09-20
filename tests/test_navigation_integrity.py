from __future__ import annotations

from types import SimpleNamespace

import app


def _choice_values(component) -> list[str]:
    return [
        str(choice[1] if isinstance(choice, tuple) else choice)
        for choice in component.choices
    ]


def test_every_scale_card_stays_inside_its_selected_category() -> None:
    all_paths = set(app._all_catalog_paths())
    categories = {(path[0], path[1]) for path in all_paths}

    for schema, modality in categories:
        selector = app._scale_selector_data(schema, modality)
        rendered_paths = []
        for branch in selector:
            for card in branch["scales"]:
                card_path = (
                    card["schema"],
                    card["modality"],
                    card["activity"],
                    card["scale"],
                )
                assert card["schema"] == schema
                assert card["modality"] == modality
                assert card["activity"] == branch["activity"]
                assert card_path in all_paths
                assert card["available"] is (
                    card_path in set(app._catalog_paths())
                )
                rendered_paths.append(card_path)

        expected_paths = [
            path
            for path in app._all_catalog_paths()
            if path[0] == schema and path[1] == modality
        ]
        assert len(rendered_paths) == len(set(rendered_paths))
        assert set(rendered_paths) == set(expected_paths)


def test_text_navigation_partitions_every_available_path_exactly() -> None:
    available_paths = set(app._catalog_paths())
    assert available_paths
    assert all(
        not app._is_sign_language_schema(path[0])
        for path in available_paths
    )

    rebuilt_paths = set()
    categories = {(path[0], path[1]) for path in available_paths}
    for schema, modality in categories:
        expected_activities = sorted(
            {
                path[2]
                for path in available_paths
                if path[0] == schema and path[1] == modality
            }
        )
        assert app._available_activities(schema, modality) == expected_activities

        for activity in expected_activities:
            expected_scales = sorted(
                {
                    path[3]
                    for path in available_paths
                    if path[:3] == (schema, modality, activity)
                }
            )
            assert (
                app._available_scales(schema, modality, activity)
                == expected_scales
            )
            rebuilt_paths.update(
                (schema, modality, activity, scale)
                for scale in expected_scales
            )

    assert rebuilt_paths == available_paths


def test_each_category_button_opens_only_its_own_scales() -> None:
    available_paths = set(app._catalog_paths())
    categories = sorted({(path[0], path[1]) for path in available_paths})

    for schema, modality in categories:
        selection = app._navigation_selection(schema, modality)
        selector, schema_box, modality_box, activity_box, scale_box, _ = selection

        assert schema_box.value == schema
        assert modality_box.value == modality
        assert activity_box.value in _choice_values(activity_box)
        assert scale_box.value in _choice_values(scale_box)
        assert (
            schema,
            modality,
            activity_box.value,
            scale_box.value,
        ) in available_paths

        for branch in selector:
            for card in branch["scales"]:
                assert card["schema"] == schema
                assert card["modality"] == modality


def test_each_available_scale_button_preserves_its_full_path() -> None:
    for path in app._catalog_paths():
        schema, modality, activity, scale = path
        result = app.scale_selector_click(
            SimpleNamespace(
                schema=schema,
                modality=modality,
                activity=activity,
                scale=scale,
            )
        )

        schema_box, modality_box, activity_box, scale_box, message = result
        assert schema_box.value == schema
        assert modality_box.value == modality
        assert activity_box.value == activity
        assert scale_box.value == scale
        assert activity in _choice_values(activity_box)
        assert scale in _choice_values(scale_box)
        assert scale in message


def test_taxonomy_available_buttons_have_a_real_participant_route() -> None:
    available_categories = {
        (path[0], path[1]) for path in app._catalog_paths()
    }

    for column in app._taxonomy_data():
        for item in column["items"]:
            route = (item["schema"], item["modality"])
            assert item["available"] is (route in available_categories)
